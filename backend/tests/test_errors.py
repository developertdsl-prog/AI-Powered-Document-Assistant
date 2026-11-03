"""Tests for the shared error envelope, including unexpected failures (Phase 5.2)."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models import User


def test_unhandled_exception_returns_the_internal_error_envelope(
    db_session: Session,
    app_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A crash answers 500 with the public envelope and logs the traceback."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def explode() -> User:
        raise RuntimeError("connection pool exploded")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: app_settings
    app.dependency_overrides[get_current_user] = explode

    try:
        # The exception handler answers before the exception keeps
        # propagating, so the client must not re-raise it.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/documents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "An unexpected error occurred."
    # The envelope must not leak internals to the caller.
    assert "connection pool exploded" not in response.text
    assert "Traceback" not in response.text

    # Operators keep the detail: the failure is logged with its traceback.
    assert any(
        record.levelname == "ERROR" and "Unhandled error" in record.getMessage()
        for record in caplog.records
    )
