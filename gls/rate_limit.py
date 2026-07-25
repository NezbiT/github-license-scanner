"""
Simple in-process sliding-window rate limiter.

Used to reduce abuse of the scan pipeline (GitHub API + registries) when the
web UI is exposed beyond localhost. Not a substitute for reverse-proxy limits
(nginx, Cloudflare, etc.) in production.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Thread-safe sliding window counter keyed by client id."""

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_calls = max_calls
        self.window_seconds = float(window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        q = self._events[key]
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if not q and key in self._events:
            # Keep empty deques small by deleting idle keys occasionally
            pass

    def allow(self, key: str) -> bool:
        """Return True and record a call if under the limit."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            q = self._events[key]
            if len(q) >= self.max_calls:
                return False
            q.append(now)
            return True

    def remaining(self, key: str) -> int:
        """How many calls remain in the current window for this key."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            return max(0, self.max_calls - len(self._events[key]))

    def retry_after_seconds(self, key: str) -> float:
        """Seconds until the oldest event exits the window (0 if allowed)."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            q = self._events[key]
            if len(q) < self.max_calls:
                return 0.0
            return max(0.0, (q[0] + self.window_seconds) - now)
