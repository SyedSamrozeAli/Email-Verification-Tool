import threading
import dns.resolver

_lock = threading.Lock()
_cache: dict[str, list[str]] = {}

_resolver = dns.resolver.Resolver()
_resolver.timeout = 5
_resolver.lifetime = 5


def resolve_mx(domain: str) -> list[str]:
    """Return MX hosts for domain, sorted by preference, lowest first.
    Falls back to the domain itself (implicit MX, RFC 5321) if no MX record
    but an A record exists. Cached per-domain, thread-safe. Empty list = no mail server."""
    domain = domain.lower()
    with _lock:
        if domain in _cache:
            return _cache[domain]

    hosts = _do_resolve(domain)

    with _lock:
        _cache[domain] = hosts
    return hosts


def _do_resolve(domain: str) -> list[str]:
    try:
        answers = _resolver.resolve(domain, "MX")
        return [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        pass
    except Exception:
        return []

    try:
        _resolver.resolve(domain, "A")
        return [domain]
    except Exception:
        return []
