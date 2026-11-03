"""In-process fixed-window rate limiting for the expensive endpoints.

Counters live in a module-level table, which is correct for a single
backend process. Moving the limit to Redis is a Phase 6 concern once
the app runs behind more than one worker.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from time import monotonic

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitExceededError
from app.models import User

_lock = threading.Lock()
_windows: dict[str, tuple[float, int]] = {}

# Drop expired windows once the table grows past this many keys so a long
# running development server cannot grow memory forever.
_MAX_TRACKED_KEYS = 10_000


def check_rate_limit(*, scope: str, key: str, settings: Settings) -> None:
    """Count one request for ``scope`` and ``key``.

    Raises ``RateLimitExceededError`` (429) once the user exceeds the
    configured requests per window for that scope.
    """

    if not settings.rate_limit_enabled:
        return

    now = monotonic()
    window = float(settings.rate_limit_window_seconds)
    window_key = f"{scope}:{key}"

    with _lock:
        started_at, count = _windows.get(window_key, (now, 0))

        if now - started_at >= window:
            # The window elapsed: start a fresh one for this key.
            started_at, count = now, 0

        count += 1
        _windows[window_key] = (started_at, count)

        if len(_windows) > _MAX_TRACKED_KEYS:
            expired = [
                tracked_key
                for tracked_key, (start, _) in _windows.items()
                if now - start >= window
            ]
            for tracked_key in expired:
                del _windows[tracked_key]

    if count > settings.rate_limit_requests:
        raise RateLimitExceededError()


def rate_limit(scope: str) -> Callable[..., None]:
    """Build a FastAPI dependency enforcing one named rate-limit bucket.

    Every user of the bucket shares one counter per scope, so asking many
    questions and generating many summaries draw from the same allowance.
    """

    def dependency(
        current_user: User = Depends(get_current_user),
        settings: Settings = Depends(get_settings),
    ) -> None:
        check_rate_limit(
            scope=scope,
            key=str(current_user.id),
            settings=settings,
        )

    return dependency
