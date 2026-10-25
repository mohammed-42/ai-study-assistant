"""Tests for the per-user in-memory rate limiter."""

import pytest
from fastapi import HTTPException

from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule, rate_limiter


@pytest.fixture(autouse=True)
def clear_rate_limits():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_allows_requests_up_to_limit():
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=2, window_seconds=60)

    await limiter.check("user-1", rule)
    await limiter.check("user-1", rule)


@pytest.mark.asyncio
async def test_rejects_request_over_limit_with_retry_after():
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=2, window_seconds=60)

    await limiter.check("user-1", rule)
    await limiter.check("user-1", rule)

    with pytest.raises(HTTPException) as exc_info:
        await limiter.check("user-1", rule)

    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_limits_are_isolated_per_key():
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)

    await limiter.check("user-1", rule)
    await limiter.check("user-2", rule)

    with pytest.raises(HTTPException):
        await limiter.check("user-1", rule)


@pytest.mark.asyncio
async def test_zero_limit_disables_rate_limiting():
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=0, window_seconds=60)

    for _ in range(100):
        await limiter.check("user-1", rule)
