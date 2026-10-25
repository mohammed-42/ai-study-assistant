"""Bounded timeouts and retries for blocking external SDK calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ExternalCallError(RuntimeError):
    """Raised after an external call exhausts its timeout/retry budget."""


async def call_with_retry(
    func: Callable[..., Any],
    *args: Any,
    timeout: float = 60,
    retries: int = 2,
    backoff: float = 0.5,
    **kwargs: Any,
) -> Any:
    """Run a blocking SDK call in a thread with a timeout and bounded retries."""
    attempts = max(0, retries)
    last_exc: Exception | None = None

    for attempt in range(attempts + 1):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=timeout,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "External call %s failed (attempt %d/%d): %s",
                getattr(func, "__name__", type(func).__name__),
                attempt + 1,
                attempts + 1,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(backoff * (2 ** attempt))

    reason = "timeout" if isinstance(last_exc, TimeoutError) else str(last_exc)
    raise ExternalCallError(
        f"External service call failed after {attempts + 1} attempt(s): {reason}"
    ) from last_exc
