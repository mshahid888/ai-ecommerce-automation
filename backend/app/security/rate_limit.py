"""In-memory sliding-window rate limiter (Phase 7).

Per client IP, per rule name. No Redis/Postgres — the demo's single
process keeps its own counters. ``time.monotonic()`` is used so clock
adjustments cannot game the windows. Thread-safe for FastAPI's
threadpool usage.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Fixed rules, sliding windows, oldest-timestamp eviction."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(
        self, key: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]:
        """Record one hit.

        Returns ``(allowed, retry_after_seconds)``. When denied,
        ``retry_after_seconds`` tells the client how long to wait; the
        429 response must surface it via the ``Retry-After`` header.
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(
                    1, math.ceil(bucket[0] + window_seconds - now)
                )
                return False, float(retry_after)
            bucket.append(now)
            if len(self._buckets) > 20_000:
                # Opportunistic cleanup: drop fully-expired buckets.
                for stale in [
                    k for k, b in self._buckets.items()
                    if not b or b[-1] <= cutoff
                ]:
                    del self._buckets[stale]
            return True, 0.0

    def reset(self) -> None:
        """Clear all counters (used by tests)."""
        with self._lock:
            self._buckets.clear()


def client_ip_from_scope(scope: dict) -> str:
    """Best-effort client IP from an ASGI scope."""
    client = scope.get("client")
    if client and client[0]:
        return str(client[0])
    return "unknown"


# Module singleton shared by the middleware. Tests reset it between cases.
limiter = SlidingWindowLimiter()
