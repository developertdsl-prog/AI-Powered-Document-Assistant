"""Tests for the health endpoint, error envelope, and DB probe."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.services.health import check_database

client = TestClient(app)


def test_health_returns_ok_when_database_is_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: True)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]
    assert body["environment"]
    assert body["checked_at"]


def test_health_returns_503_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: False)

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "down"


def test_root_returns_service_information() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["health"] == "/api/health"
    assert body["docs"] == "/docs"


def test_unknown_route_uses_error_envelope() -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]


def test_check_database_reports_success_for_reachable_database() -> None:
    engine = create_engine("sqlite://")

    assert check_database(engine) is True

    engine.dispose()


def test_check_database_reports_failure_for_unreachable_database() -> None:
    class BrokenEngine:
        def connect(self) -> None:
            raise SQLAlchemyError("connection refused")

    assert check_database(BrokenEngine()) is False  # type: ignore[arg-type]
