"""In-memory per-user rate limiting for expensive endpoints.

This is intentionally simple and process-local. It protects a single API
instance from accidental bursts; multi-instance deployments should use a
shared store (for example Redis) with the same helper interface.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int = 60


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def check(self, key: str, rule: RateLimitRule) -> None:
        if rule.limit <= 0:
            return

        now = time.monotonic()
        cutoff = now - rule.window_seconds

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.limit:
                retry_after = max(1, int(bucket[0] + rule.window_seconds - now + 0.999))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = InMemoryRateLimiter()


async def enforce_rate_limit(scope: str, user_id: uuid.UUID, setting_name: str) -> None:
    """Enforce a per-user, per-scope limit read from settings at call time."""
    limit = int(getattr(settings, setting_name, 0) or 0)
    await rate_limiter.check(
        f"{scope}:{user_id}",
        RateLimitRule(limit=limit, window_seconds=60),
    )
