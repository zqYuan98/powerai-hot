"""Small, bounded in-process rate limits for sensitive and costly operations.

This protects a single application process. Production deployments still need a
reverse proxy (or another shared service) for distributed/IP-level limiting.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable
from ipaddress import ip_address, ip_network
import threading
import time

from fastapi import HTTPException, Request

from core.config import settings


UNLOCK_LIMIT = 5
HIGH_COST_LIMIT = 3
RATE_LIMIT_WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENT_OPERATIONS = 1024


class SlidingWindowLimiter:
    """Lock-protected sliding window keyed by operation and client identity."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        max_keys: int = MAX_TRACKED_CLIENT_OPERATIONS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit <= 0 or window_seconds <= 0 or max_keys <= 0:
            raise ValueError("rate limiter bounds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._events: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._events)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def allow(self, operation: str, identity: str) -> bool:
        now = self._clock()
        cutoff = now - self.window_seconds
        key = (operation, identity)

        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_keys:
                    self._events.popitem(last=False)
                events = deque()
                self._events[key] = events
            else:
                self._events.move_to_end(key)

            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


unlock_limiter = SlidingWindowLimiter(
    limit=UNLOCK_LIMIT,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)
high_cost_limiter = SlidingWindowLimiter(
    limit=HIGH_COST_LIMIT,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _client_identity(request: Request) -> str:
    peer_text = request.client.host if request.client is not None else "unknown"
    try:
        peer = ip_address(peer_text)
    except ValueError:
        return peer_text

    trusted = False
    for cidr in settings.trusted_proxy_cidrs:
        try:
            if peer in ip_network(cidr, strict=False):
                trusted = True
                break
        except ValueError:
            # Settings validates production values; ignore unsafe runtime patches.
            continue
    if not trusted:
        return peer.compressed

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return peer.compressed
    candidate = forwarded_for.split(",", 1)[0].strip()
    try:
        return ip_address(candidate).compressed
    except ValueError:
        return peer.compressed


def enforce_rate_limit(
    request: Request,
    operation: str,
    *,
    unlock: bool = False,
) -> None:
    limiter = unlock_limiter if unlock else high_cost_limiter
    if limiter.allow(operation, _client_identity(request)):
        return
    raise HTTPException(
        status_code=429,
        detail="Too many requests",
        headers={"Retry-After": str(int(limiter.window_seconds))},
    )


def reset_rate_limits() -> None:
    """Clear process-local state so isolated app/test lifecycles do not leak."""
    unlock_limiter.reset()
    high_cost_limiter.reset()
