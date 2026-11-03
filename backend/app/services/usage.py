"""Usage counters for AI calls (Phase 5.3).

Every answer, summary, extraction, and embedding call is timed and
counted per operation and provider, in process memory. The snapshot
exposed by ``GET /api/usage`` shows how much AI work the API did, how
much of it failed, and how long it took, without keeping per-user data
or writing anywhere.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter


@dataclass
class _Counter:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0


class UsageTracker:
    """Thread-safe counters for one process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = datetime.now(UTC)
        self._counters: dict[tuple[str, str], _Counter] = {}

    def record(
        self,
        *,
        operation: str,
        provider: str,
        ok: bool,
        duration_ms: float,
    ) -> None:
        """Count one call of ``operation`` against ``provider``."""

        with self._lock:
            counter = self._counters.setdefault((operation, provider), _Counter())
            counter.total += 1
            counter.succeeded += int(ok)
            counter.failed += int(not ok)
            counter.total_duration_ms += duration_ms

    def snapshot(self) -> dict[str, object]:
        """Return the recorded counters as JSON-ready data."""

        with self._lock:
            calls = [
                {
                    "operation": operation,
                    "provider": provider,
                    "total": counter.total,
                    "succeeded": counter.succeeded,
                    "failed": counter.failed,
                    "total_duration_ms": round(counter.total_duration_ms, 1),
                    "average_duration_ms": round(
                        counter.total_duration_ms / counter.total, 1
                    ),
                }
                for (operation, provider), counter in sorted(self._counters.items())
            ]
            return {"since": self._started_at, "calls": calls}

    def reset(self) -> None:
        """Forget the recorded counters and start a new window."""

        with self._lock:
            self._started_at = datetime.now(UTC)
            self._counters.clear()


# One tracker per process, like the rate-limit table: correct for a
# single backend and revisited when the app runs multiple workers.
_tracker = UsageTracker()


def get_usage_tracker() -> UsageTracker:
    """Return the process-wide usage tracker."""

    return _tracker


@contextmanager
def record_ai_call(operation: str, provider: str) -> Iterator[None]:
    """Count one AI call, including how long it took and whether it failed."""

    tracker = get_usage_tracker()
    started = perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        tracker.record(
            operation=operation,
            provider=provider,
            ok=ok,
            duration_ms=(perf_counter() - started) * 1000,
        )
