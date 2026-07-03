# (provider_name, substrings matched against MX hostnames, reliable)
# "reliable" providers give a trustworthy 250/550 at RCPT time.
# "not reliable" providers are known to accept-all at RCPT and bounce later,
# so a 250 from them must NOT be trusted as a confirmed mailbox.
_PROVIDER_PATTERNS = [
    ("google", ("google.com", "googlemail.com"), True),
    ("outlook365", ("outlook.com", "protection.outlook.com"), True),
    ("zoho", ("zoho.com", "zohomail.com"), True),
    ("icloud", ("icloud.com",), True),
    ("proton", ("protonmail.ch", "proton.me"), True),
    ("fastmail", ("messagingengine.com",), True),
    ("yahoo", ("yahoodns.net",), False),
    ("aol", ("aol.com",), False),
    ("verizon", ("verizon.net",), False),
]


def provider_for_mx(mx_hosts: list[str]):
    """Returns (provider_name, reliable:bool). Unknown providers default to
    reliable=True (no evidence they accept-all; trust the SMTP response)."""
    for host in mx_hosts:
        h = host.lower()
        for name, patterns, reliable in _PROVIDER_PATTERNS:
            if any(p in h for p in patterns):
                return name, reliable
    return "unknown", True
