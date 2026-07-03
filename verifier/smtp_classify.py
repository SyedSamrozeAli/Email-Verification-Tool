UNKNOWN_HINTS = (
    "does not exist", "doesn't exist", "no such user", "user unknown",
    "unknown user", "not found", "no mailbox", "invalid recipient",
    "user not found", "recipient rejected", "no such recipient",
    "unknown recipient", "account that you tried to reach",
)
FULL_HINTS = ("quota", "full", "over limit", "over quota", "storage")
BLOCKED_HINTS = (
    "blocked", "spam", "denied", "policy", "blacklist", "reputation",
    "refused", "not authorized", "unauthorized",
)
DISABLED_HINTS = ("disabled", "inactive", "suspended", "deactivated")
GREYLIST_HINTS = ("greylist", "grey list", "try again later", "try later", "temporarily deferred")
RATE_LIMIT_HINTS = ("rate", "too many", "throttl", "too fast")


def _has_any(text: str, hints) -> bool:
    return any(h in text for h in hints)


def classify(code, text: str) -> str:
    """Turn an SMTP (code, text) pair into a coarse reason:
    ok, user_unknown, mailbox_full, blocked, disabled, greylisted,
    rate_limited, or unreachable/unknown."""
    if code is None:
        return "unreachable"

    text_l = (text or "").lower()

    if code == 250:
        return "ok"

    if code == 421:
        return "rate_limited"

    if code in (450, 451, 452):
        if _has_any(text_l, GREYLIST_HINTS):
            return "greylisted"
        if _has_any(text_l, FULL_HINTS):
            return "mailbox_full"
        if _has_any(text_l, RATE_LIMIT_HINTS):
            return "rate_limited"
        return "greylisted"

    if code == 552:
        return "mailbox_full"

    if code in (550, 551, 553, 554):
        if _has_any(text_l, UNKNOWN_HINTS):
            return "user_unknown"
        if _has_any(text_l, FULL_HINTS):
            return "mailbox_full"
        if _has_any(text_l, BLOCKED_HINTS):
            return "blocked"
        if _has_any(text_l, DISABLED_HINTS):
            return "disabled"
        return "user_unknown"

    return "unknown"
