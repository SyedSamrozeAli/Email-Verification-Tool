import threading
import time
from contextlib import contextmanager

from . import config


class DomainThrottle:
    """Caps concurrent SMTP sessions per domain and enforces a minimum delay
    between connection attempts to the same domain, so a worker pool never
    hammers one mail server (which triggers rate-limit 4xx -> false unknowns)."""

    def __init__(self, max_concurrent: int, delay_s: float):
        self.max_concurrent = max_concurrent
        self.delay_s = delay_s
        self._sem_lock = threading.Lock()
        self._semaphores: dict[str, threading.Semaphore] = {}
        self._last_hit_lock = threading.Lock()
        self._last_hit: dict[str, float] = {}

    def _semaphore_for(self, domain: str) -> threading.Semaphore:
        with self._sem_lock:
            sem = self._semaphores.get(domain)
            if sem is None:
                sem = threading.Semaphore(self.max_concurrent)
                self._semaphores[domain] = sem
            return sem

    def _wait_for_slot(self, domain: str):
        while True:
            with self._last_hit_lock:
                now = time.time()
                elapsed = now - self._last_hit.get(domain, 0.0)
                if elapsed >= self.delay_s:
                    self._last_hit[domain] = now
                    return
                wait = self.delay_s - elapsed
            time.sleep(wait)

    @contextmanager
    def acquire(self, domain: str):
        domain = domain.lower()
        sem = self._semaphore_for(domain)
        sem.acquire()
        try:
            self._wait_for_slot(domain)
            yield
        finally:
            sem.release()


_default_throttle = None
_default_lock = threading.Lock()


def default_throttle() -> DomainThrottle:
    global _default_throttle
    with _default_lock:
        if _default_throttle is None:
            _default_throttle = DomainThrottle(
                max_concurrent=config.get("per_domain_max_concurrent"),
                delay_s=config.get("per_domain_delay_s"),
            )
        return _default_throttle
