import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config
from .normalize import normalize
from .syntax import check_syntax
from .typo import suggest_domain
from .lists import disposable_domains, free_providers, role_prefixes
from .dns_mx import resolve_mx
from .dns_signals import has_spf, has_dmarc
from .smtp_probe import is_smtp_available
from .providers import provider_for_mx
from .smtp_classify import classify
from .catchall import probe as catchall_probe
from .gravatar import has_gravatar
from .result import EmailResult, VALID, INVALID, RISKY, UNKNOWN

RETRYABLE_REASONS = {"greylisted", "rate_limited"}


def _offline_confidence(has_typo: bool) -> int:
    return 40 if has_typo else 70


def _signal_bonus(spf: bool, dmarc: bool, gravatar) -> int:
    bonus = 0
    if spf:
        bonus += 5
    if dmarc:
        bonus += 5
    if gravatar is True:
        bonus += 10
    elif gravatar is False:
        bonus -= 5
    return bonus


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def verify_email(raw_email: str) -> EmailResult:
    email = normalize(raw_email)
    result = EmailResult(email=email or raw_email)

    if not email:
        result.status, result.reason = INVALID, "empty_email"
        return result

    ok, normalized, error = check_syntax(email)
    if not ok:
        result.status, result.reason = INVALID, "bad_syntax"
        return result
    email = normalized
    result.email = email

    local, _, domain = email.partition("@")
    domain_lower = domain.lower()

    result.did_you_mean = suggest_domain(domain_lower)
    result.is_disposable = domain_lower in disposable_domains()
    result.is_free = domain_lower in free_providers()
    result.is_role = local.lower() in role_prefixes()

    if result.is_disposable:
        result.status, result.reason, result.confidence = INVALID, "disposable_domain", 0
        return result

    mx_hosts = resolve_mx(domain_lower)
    if not mx_hosts:
        result.status, result.reason, result.confidence = INVALID, "no_mx", 0
        return result
    result.mx_host = mx_hosts[0]

    provider_name, reliable = provider_for_mx(mx_hosts)
    result.provider = provider_name
    result.reliable = reliable

    result.has_spf = has_spf(domain_lower)
    result.has_dmarc = has_dmarc(domain_lower)

    offline_conf = _offline_confidence(bool(result.did_you_mean))

    if not is_smtp_available():
        result.status, result.reason = UNKNOWN, "smtp_unavailable"
        result.confidence = _clamp(offline_conf + _signal_bonus(result.has_spf, result.has_dmarc, None))
        return result

    probe_result = catchall_probe(domain_lower, mx_hosts, email)
    if probe_result["mx_host"]:
        result.mx_host = probe_result["mx_host"]
    result.is_catch_all = bool(probe_result["catch_all"])

    target_code = probe_result["target_code"]
    target_text = probe_result["target_text"]
    result.smtp_message = (target_text or "")[:200]

    if target_code is None:
        result.status, result.reason = UNKNOWN, "smtp_unreachable"
        result.confidence = _clamp(offline_conf + _signal_bonus(result.has_spf, result.has_dmarc, None))
        return result

    reason_key = classify(target_code, target_text)

    if probe_result["catch_all"] is True:
        gravatar = has_gravatar(email)
        result.has_gravatar = gravatar
        result.status, result.reason = RISKY, "catch_all"
        result.confidence = _clamp(50 + _signal_bonus(result.has_spf, result.has_dmarc, gravatar) - 10)
        return result

    if reason_key == "ok":
        if not reliable:
            gravatar = has_gravatar(email)
            result.has_gravatar = gravatar
            result.status, result.reason = RISKY, "provider_accepts_all"
            result.confidence = _clamp(40 + _signal_bonus(result.has_spf, result.has_dmarc, gravatar))
        else:
            result.status, result.reason, result.confidence = VALID, "smtp_ok", 100
        return result

    if reason_key == "user_unknown":
        result.status, result.reason, result.confidence = INVALID, "smtp_user_unknown", 0
        return result

    if reason_key == "mailbox_full":
        result.status, result.reason, result.confidence = VALID, "smtp_mailbox_full", 70
        return result

    if reason_key == "disabled":
        result.status, result.reason, result.confidence = INVALID, "smtp_disabled", 10
        return result

    if reason_key == "blocked":
        gravatar = has_gravatar(email)
        result.has_gravatar = gravatar
        result.status, result.reason = UNKNOWN, "smtp_blocked"
        result.confidence = _clamp(offline_conf + _signal_bonus(result.has_spf, result.has_dmarc, gravatar))
        return result

    # greylisted / rate_limited / unknown -> retryable in pass 2
    result.status, result.reason = UNKNOWN, reason_key
    result.confidence = _clamp(offline_conf + _signal_bonus(result.has_spf, result.has_dmarc, None))
    return result


def _domain_key(raw_email: str) -> str:
    return raw_email.strip().lower().rpartition("@")[2]


def _verify_rows(rows, email_field, indices, on_progress, should_cancel, progress_offset, progress_total):
    """Runs verify_email for the given row indices concurrently, domain-grouped
    for cache locality. Returns {index: EmailResult}."""
    order = sorted(indices, key=lambda i: _domain_key(rows[i].get(email_field, "") or "") if email_field else "")

    out = {}
    completed = progress_offset
    with ThreadPoolExecutor(max_workers=config.get("max_workers")) as executor:
        futures = {}
        for i in order:
            if should_cancel and should_cancel():
                break
            raw = (rows[i].get(email_field) or "").strip() if email_field else ""
            futures[executor.submit(verify_email, raw)] = i

        for future in as_completed(futures):
            i = futures[future]
            try:
                out[i] = future.result()
            except Exception:
                out[i] = EmailResult(email=rows[i].get(email_field, ""), status=INVALID, reason="internal_error")
            completed += 1
            if on_progress:
                on_progress(completed, progress_total, out[i])
    return out


def run_batch(rows: list[dict], email_field: str, on_progress=None, should_cancel=None, on_phase=None):
    """Two-pass verification. Pass 1 verifies every row. Rows that come back
    'unknown' with a retryable reason (greylisted / rate_limited) are queued
    and re-verified in pass 2 after a delay, recovering mailboxes that a
    single-pass check would have lost. Returns a list aligned to `rows`."""
    n = len(rows)
    all_indices = list(range(n))

    if on_phase:
        on_phase("pass1", {"total": n})

    pass1_results = _verify_rows(rows, email_field, all_indices, on_progress, should_cancel, 0, n)
    results: list[EmailResult | None] = [pass1_results.get(i) for i in range(n)]

    retry_indices = [
        i for i, r in enumerate(results)
        if r is not None and r.status == UNKNOWN and r.reason in RETRYABLE_REASONS
    ]

    if config.get("enable_second_pass") and retry_indices and not (should_cancel and should_cancel()):
        delay = config.get("greylist_retry_delay_s")
        if on_phase:
            on_phase("waiting", {"retry_count": len(retry_indices), "delay_s": delay})
        waited = 0.0
        while waited < delay:
            if should_cancel and should_cancel():
                break
            step = min(1.0, delay - waited)
            time.sleep(step)
            waited += step

        if not (should_cancel and should_cancel()):
            if on_phase:
                on_phase("pass2", {"retry_count": len(retry_indices)})
            pass2_results = _verify_rows(
                rows, email_field, retry_indices, on_progress, should_cancel,
                n, n + len(retry_indices),
            )
            for i, r in pass2_results.items():
                results[i] = r

    if on_phase:
        on_phase("done", {})

    return results
