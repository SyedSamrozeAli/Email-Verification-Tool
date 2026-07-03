from email_validator import validate_email, EmailNotValidError


def check_syntax(email: str):
    """RFC-grade syntax check. Returns (ok, normalized_email_or_None, error_or_None).

    check_deliverability=False: DNS/MX is handled separately (and cached) by dns_mx.py.
    """
    try:
        result = validate_email(email, check_deliverability=False, allow_smtputf8=True)
        return True, result.normalized, None
    except EmailNotValidError as e:
        return False, None, str(e)
