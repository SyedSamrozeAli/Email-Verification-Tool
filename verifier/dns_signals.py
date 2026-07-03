import threading
import dns.resolver

_lock = threading.Lock()
_spf_cache: dict[str, bool] = {}
_dmarc_cache: dict[str, bool] = {}

_resolver = dns.resolver.Resolver()
_resolver.timeout = 5
_resolver.lifetime = 5


def _txt_records(name: str) -> list[str]:
    try:
        answers = _resolver.resolve(name, "TXT")
        records = []
        for r in answers:
            # dnspython TXT records may be split into multiple byte-strings
            records.append(b"".join(r.strings).decode("utf-8", errors="replace"))
        return records
    except Exception:
        return []


def has_spf(domain: str) -> bool:
    domain = domain.lower()
    with _lock:
        if domain in _spf_cache:
            return _spf_cache[domain]

    result = any(r.lower().startswith("v=spf1") for r in _txt_records(domain))

    with _lock:
        _spf_cache[domain] = result
    return result


def has_dmarc(domain: str) -> bool:
    domain = domain.lower()
    with _lock:
        if domain in _dmarc_cache:
            return _dmarc_cache[domain]

    result = any(r.lower().startswith("v=dmarc1") for r in _txt_records(f"_dmarc.{domain}"))

    with _lock:
        _dmarc_cache[domain] = result
    return result
