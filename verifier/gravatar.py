import hashlib
import threading
import urllib.request
import urllib.error

from . import config

_lock = threading.Lock()
_cache: dict[str, bool | None] = {}


def has_gravatar(email: str) -> bool | None:
    """Best-effort existence check via Gravatar's free, unauthenticated API.
    Returns True/False, or None if the check couldn't be completed (network
    error, timeout, or disabled via config) - never treated as a negative
    signal on failure."""
    if not config.get("enable_gravatar"):
        return None

    key = email.strip().lower()
    with _lock:
        if key in _cache:
            return _cache[key]

    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{digest}?d=404"
    result = None
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=config.get("gravatar_timeout_s")) as resp:
            result = resp.status == 200
    except urllib.error.HTTPError as e:
        result = e.code == 200
    except Exception:
        result = None

    with _lock:
        _cache[key] = result
    return result
