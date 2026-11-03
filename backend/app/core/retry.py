"""Retry policy for transient AI provider failures (Phase 5.3).

Provider calls travel over the network, where a timeout, a rate limit, or
a gateway hiccup is normal and usually gone a moment later. Retrying
those short-lived failures with exponential backoff keeps a flaky
upstream from surfacing as a ``503``, while permanent client errors (bad
key, bad request) still fail on the first attempt.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)

# 408 request timeout, 425 too-early, 429 rate limit, and the
# server/gateway errors a load balancer can produce while an instance
# restarts.
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


def is_retryable(status_code: int) -> bool:
    """Report whether an HTTP status is worth another attempt."""

    return status_code in RETRYABLE_STATUS_CODES


def request_with_retries(
    send: Callable[[], httpx.Response],
    *,
    max_retries: int,
    backoff_seconds: float,
    operation: str = "provider request",
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Call ``send`` and retry transient failures with exponential backoff.

    When the attempts run out, transport errors are re-raised and
    retryable responses are returned to the caller, so the caller keeps
    producing its own typed error (``LLMError``, ``EmbeddingError``).
    Non-retryable statuses are returned immediately.
    """

    budget = max(0, int(max_retries))
    attempt = 0

    while True:
        try:
            response = send()
        except httpx.HTTPError as exc:
            if attempt >= budget:
                raise
            kind = "transport error"
            reason = str(exc) or type(exc).__name__
        else:
            if not is_retryable(response.status_code) or attempt >= budget:
                return response
            kind = "HTTP status"
            reason = f"HTTP {response.status_code}"

        delay = max(0.0, backoff_seconds * (2**attempt))
        attempt += 1
        logger.warning(
            "%s failed with %s; retrying in %.2fs (attempt %d/%d)",
            operation,
            kind,
            delay,
            attempt,
            budget + 1,
            extra={
                "event": "provider_retry",
                "operation": operation,
                "reason": reason,
                "attempt": attempt,
                "max_attempts": budget + 1,
                "delay_seconds": round(delay, 3),
            },
        )
        if delay > 0:
            sleep(delay)
