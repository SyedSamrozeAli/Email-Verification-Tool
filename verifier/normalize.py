import re

_MAILTO_RE = re.compile(r"^mailto:", re.IGNORECASE)


def normalize(raw: str) -> str:
    """Trim whitespace, strip a leading mailto:, lowercase the domain part."""
    if not raw:
        return ""
    email = _MAILTO_RE.sub("", raw.strip())
    email = email.strip().strip("<>").strip()
    if "@" not in email:
        return email
    local, _, domain = email.rpartition("@")
    return f"{local}@{domain.lower()}"
