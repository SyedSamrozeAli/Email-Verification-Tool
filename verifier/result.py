from dataclasses import dataclass, asdict

VALID = "valid"
INVALID = "invalid"
RISKY = "risky"
UNKNOWN = "unknown"


@dataclass
class EmailResult:
    email: str
    status: str = UNKNOWN
    reason: str = ""
    confidence: int = 0
    is_role: bool = False
    is_disposable: bool = False
    is_free: bool = False
    is_catch_all: bool = False
    did_you_mean: str = ""
    mx_host: str = ""
    provider: str = ""
    smtp_message: str = ""
    has_spf: bool | None = None
    has_dmarc: bool | None = None
    has_gravatar: bool | None = None
    reliable: bool | None = None

    def as_row(self) -> dict:
        d = asdict(self)
        d.pop("email")
        return d


RESULT_COLUMNS = [
    "status", "reason", "confidence",
    "is_role", "is_disposable", "is_free", "is_catch_all",
    "did_you_mean", "mx_host", "provider", "smtp_message",
    "has_spf", "has_dmarc", "has_gravatar", "reliable",
]
