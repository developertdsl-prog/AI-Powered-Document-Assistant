"""Concurrency tests for rate limiting, usage counters, and requests (Phase 5.3)."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import check_rate_limit
from app.services.usage import get_usage_tracker


def test_rate_limit_admits_exactly_the_allowance_under_concurrency() -> None:
    """Parallel requests cannot slip past or lose the shared counter."""

    settings = Settings(
        jwt_secret_key="concurrency-test-secret-key-32-bytes",
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
    )
    key = f"concurrency-{uuid.uuid4()}"

    def attempt() -> bool:
        try:
            check_rate_limit(scope="ai", key=key, settings=settings)
        except RateLimitExceededError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _index: attempt(), range(60)))

    assert sum(results) == 10


def test_usage_tracker_counts_concurrent_records() -> None:
    tracker = get_usage_tracker()
    tracker.reset()

    def worker() -> None:
        for _ in range(50):
            tracker.record(
                operation="answer",
                provider="extractive",
                ok=True,
                duration_ms=1.0,
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _index: worker(), range(8)))

    (call,) = tracker.snapshot()["calls"]
    assert call["total"] == 400
    assert call["succeeded"] == 400
    assert call["failed"] == 0
    assert call["total_duration_ms"] == 400.0


def test_concurrent_requests_all_succeed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: True)

    def request_status() -> int:
        return client.get("/api/health").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _index: request_status(), range(32)))

    assert statuses == [200] * 32
