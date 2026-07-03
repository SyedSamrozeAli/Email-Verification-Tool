import json
import os
import socket
from functools import lru_cache

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "verifier_config.json")

_DEFAULTS = {
    # SMTP identity. Defaults to this machine's hostname (safe: the prober never
    # sends DATA, so no mail is ever transmitted and no domain reputation is at risk).
    # Set "helo_hostname" to a domain you own in verifier_config.json if you prefer.
    "helo_hostname": None,  # None => auto (socket.getfqdn())
    "mail_from_user": "verify",

    "max_workers": 15,
    "per_domain_max_concurrent": 2,
    "per_domain_delay_s": 1.0,
    "connect_timeout": 8,

    "catchall_probe_count": 2,

    "enable_second_pass": True,
    "greylist_retry_delay_s": 90,

    "enable_gravatar": True,
    "gravatar_timeout_s": 3,
}


@lru_cache(maxsize=1)
def _load() -> dict:
    cfg = dict(_DEFAULTS)
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def get(key: str):
    return _load()[key]


@lru_cache(maxsize=1)
def helo_hostname() -> str:
    configured = get("helo_hostname")
    if configured:
        return configured
    try:
        fqdn = socket.getfqdn()
        if fqdn and "." in fqdn and not fqdn.startswith("localhost"):
            return fqdn
    except Exception:
        pass
    return "verifier.local"


def mail_from() -> str:
    return f"{get('mail_from_user')}@{helo_hostname()}"
