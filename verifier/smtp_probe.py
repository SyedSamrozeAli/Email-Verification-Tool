import smtplib
import socket
import threading

from . import config
from .throttle import default_throttle

_availability_lock = threading.Lock()
_availability_cache = {}


def is_smtp_available() -> bool:
    """Detect once whether outbound port 25 is actually usable from this network.
    Most residential ISPs block it, which makes live SMTP mailbox checks impossible."""
    with _availability_lock:
        if "value" in _availability_cache:
            return _availability_cache["value"]

    ok = False
    try:
        with socket.create_connection(("gmail-smtp-in.l.google.com", 25), timeout=config.get("connect_timeout")):
            ok = True
    except Exception:
        ok = False

    with _availability_lock:
        _availability_cache["value"] = ok
    return ok


class SMTPSession:
    """One live SMTP conversation: EHLO once, MAIL FROM once, then any number
    of RCPT TO probes. Keeping everything on one connection means the target
    address is judged in the same context as the catch-all probes."""

    def __init__(self, host: str):
        self.host = host
        self._server = smtplib.SMTP(timeout=config.get("connect_timeout"))
        self._server.connect(host, 25)
        try:
            code, _ = self._server.ehlo(config.helo_hostname())
            if code >= 400:
                self._server.helo(config.helo_hostname())
        except smtplib.SMTPException:
            self._server.helo(config.helo_hostname())
        self._server.mail(config.mail_from())

    def rcpt(self, address: str):
        """Returns (code:int, text:str)."""
        code, text = self._server.rcpt(address)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        return code, text

    def close(self):
        try:
            self._server.quit()
        except Exception:
            try:
                self._server.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _open_session(mx_hosts: list[str]):
    """Try MX hosts in preference order; return an open SMTPSession or None
    if every host is unreachable."""
    for host in mx_hosts:
        try:
            return SMTPSession(host)
        except Exception:
            continue
    return None


def probe_domain_full(domain: str, mx_hosts: list[str], target_email: str, probe_count: int):
    """One throttled session covering: postmaster reliability check, N random
    catch-all probes, then the real target. Returns a dict:
      {mx_host, postmaster:(code,text), catchall_probes:[(code,text),...], target:(code,text)}
    or None if the domain was completely unreachable."""
    import uuid

    with default_throttle().acquire(domain):
        session = _open_session(mx_hosts)
        if session is None:
            return None
        try:
            postmaster = _safe_rcpt(session, f"postmaster@{domain}")
            catchall_probes = [
                _safe_rcpt(session, f"verify-nonexistent-{uuid.uuid4().hex[:16]}@{domain}")
                for _ in range(probe_count)
            ]
            target = _safe_rcpt(session, target_email)
            return {
                "mx_host": session.host,
                "postmaster": postmaster,
                "catchall_probes": catchall_probes,
                "target": target,
            }
        finally:
            session.close()


def probe_target_only(domain: str, mx_hosts: list[str], target_email: str):
    """Lightweight single-connection probe of just the target address, used
    once a domain's catch-all facts are already cached. Returns
    {mx_host, target:(code,text)} or None if unreachable."""
    with default_throttle().acquire(domain):
        session = _open_session(mx_hosts)
        if session is None:
            return None
        try:
            target = _safe_rcpt(session, target_email)
            return {"mx_host": session.host, "target": target}
        finally:
            session.close()


def _safe_rcpt(session: SMTPSession, address: str):
    try:
        return session.rcpt(address)
    except Exception:
        return (None, "")
