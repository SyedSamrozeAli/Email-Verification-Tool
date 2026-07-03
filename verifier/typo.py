from .lists import common_domains

_MAX_DISTANCE = 2


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def suggest_domain(domain: str) -> str:
    """Return a suggested correct domain if `domain` is a likely typo of a common
    provider, else ''. Never auto-corrects — suggestion only."""
    domain = domain.lower()
    if domain in common_domains():
        return ""

    best_domain, best_dist = "", _MAX_DISTANCE + 1
    for candidate in common_domains():
        if abs(len(candidate) - len(domain)) > _MAX_DISTANCE:
            continue
        dist = _levenshtein(domain, candidate)
        if dist < best_dist:
            best_domain, best_dist = candidate, dist

    if 0 < best_dist <= _MAX_DISTANCE:
        return best_domain
    return ""
