import threading

from .smtp_probe import probe_domain_full, probe_target_only
from . import config

_lock = threading.Lock()
_facts_cache: dict[str, dict] = {}


def probe(domain: str, mx_hosts: list[str], target_email: str) -> dict:
    """Returns {'catch_all': bool|None, 'target_code': int|None, 'target_text': str,
    'mx_host': str|None}.

    The first email seen for a domain runs a full single-session probe
    (postmaster + N random catch-all addresses + the target) and caches the
    domain-level catch-all fact. Every subsequent email for that domain reuses
    the cached fact and only opens a lightweight session for its own target
    address (never cached - address-specific)."""
    domain = domain.lower()

    with _lock:
        cached = _facts_cache.get(domain)

    if cached is None:
        full = probe_domain_full(domain, mx_hosts, target_email, config.get("catchall_probe_count"))
        if full is None:
            return {"catch_all": None, "target_code": None, "target_text": "", "mx_host": None}

        probe_codes = [code for code, _ in full["catchall_probes"]]
        reachable_codes = [c for c in probe_codes if c is not None]
        if reachable_codes and all(c == 250 for c in reachable_codes):
            catch_all = True
        elif reachable_codes:
            catch_all = False
        else:
            catch_all = None  # every catch-all probe was unreachable

        with _lock:
            _facts_cache[domain] = {"catch_all": catch_all}

        target_code, target_text = full["target"]
        return {
            "catch_all": catch_all,
            "target_code": target_code,
            "target_text": target_text,
            "mx_host": full["mx_host"],
        }

    result = probe_target_only(domain, mx_hosts, target_email)
    if result is None:
        return {"catch_all": cached["catch_all"], "target_code": None, "target_text": "", "mx_host": None}

    target_code, target_text = result["target"]
    return {
        "catch_all": cached["catch_all"],
        "target_code": target_code,
        "target_text": target_text,
        "mx_host": result["mx_host"],
    }
