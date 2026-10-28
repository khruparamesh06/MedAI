"""
In-process sliding-window rate limiting.

Limits are kept in memory, so they apply per backend process. For multi-instance deployments add an
equivalent limit at the reverse proxy / API gateway (see docs/DEPLOYMENT.md). The client IP comes
from the ASGI scope; uvicorn only rewrites it from X-Forwarded-For for proxies listed in
FORWARDED_ALLOW_IPS, so clients cannot spoof it.
"""
import logging
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger("medai.security")

# (limit, window seconds)
LOGIN_ATTEMPTS_PER_IP = 30
LOGIN_IP_WINDOW = 5 * 60
LOGIN_FAILURES_PER_ACCOUNT = 5
LOGIN_ACCOUNT_WINDOW = 15 * 60
REGISTRATIONS_PER_IP = 10
REGISTRATION_WINDOW = 60 * 60
UPLOADS_PER_USER = 30
ANALYSES_PER_USER = 60
PASSWORD_CHANGES_PER_USER = 10
HOURLY = 60 * 60


class SlidingWindow:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: int, now: float) -> deque[float]:
        events = self._events[key]
        while events and events[0] <= now - window:
            events.popleft()
        return events

    def retry_after(self, key: str, limit: int, window: int) -> int | None:
        """Seconds until another event is allowed, or None if under the limit (does not record)."""
        now = time.monotonic()
        with self._lock:
            events = self._prune(key, window, now)
            if len(events) < limit:
                return None
            return max(1, math.ceil(events[0] + window - now))

    def record(self, key: str) -> None:
        with self._lock:
            self._events[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = SlidingWindow()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many(retry_after: int, what: str) -> HTTPException:
    minutes = max(1, math.ceil(retry_after / 60))
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                         f"Too many {what}. Please try again in about {minutes} minute(s).",
                         headers={"Retry-After": str(retry_after)})


def enforce(key: str, limit: int, window: int, what: str, record: bool = True) -> None:
    """Raise 429 if `key` is over its limit; otherwise optionally record this event."""
    if not get_settings().rate_limit_enabled:
        return
    wait = limiter.retry_after(key, limit, window)
    if wait is not None:
        logger.warning("rate limit hit: %s", key.split(":", 1)[0])
        raise _too_many(wait, what)
    if record:
        limiter.record(key)


# ---- login helpers: failures are counted per account, attempts per IP ----
def check_login_allowed(request: Request, email: str) -> None:
    enforce(f"login-ip:{client_ip(request)}", LOGIN_ATTEMPTS_PER_IP, LOGIN_IP_WINDOW, "sign-in attempts")
    enforce(f"login-fail:{email}", LOGIN_FAILURES_PER_ACCOUNT, LOGIN_ACCOUNT_WINDOW,
            "failed sign-in attempts for this account", record=False)


def record_login_failure(request: Request, email: str) -> None:
    if get_settings().rate_limit_enabled:
        limiter.record(f"login-fail:{email}")
    logger.info("failed sign-in from %s", client_ip(request))


def record_login_success(email: str) -> None:
    limiter.clear(f"login-fail:{email}")
