"""Tests for bounded external-call timeouts and retries."""

import time

import pytest

from app.core.resilience import ExternalCallError, call_with_retry


def _fail_once(calls):
    calls.append(1)
    if len(calls) == 1:
        raise RuntimeError("temporary failure")
    return "ok"


@pytest.mark.asyncio
async def test_returns_result_without_retry():
    result = await call_with_retry(lambda: "ok", timeout=1, retries=2)
    assert result == "ok"


@pytest.mark.asyncio
async def test_retries_transient_failure():
    calls = []
    result = await call_with_retry(_fail_once, calls, timeout=1, retries=2, backoff=0)
    assert result == "ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_raises_after_retry_budget_exhausted():
    calls = []

    def always_fail():
        calls.append(1)
        raise RuntimeError("still failing")

    with pytest.raises(ExternalCallError, match="3 attempt"):
        await call_with_retry(always_fail, timeout=1, retries=2, backoff=0)

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_timeout_is_enforced():
    def slow_call():
        time.sleep(0.05)
        return "late"

    with pytest.raises(ExternalCallError, match="timeout"):
        await call_with_retry(slow_call, timeout=0.001, retries=0)
