"""Tests for structured logging and request correlation (Phase 5.3)."""

import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import JsonFormatter, configure_logging


def test_json_formatter_serializes_message_and_extra_fields() -> None:
    record = logging.LogRecord(
        name="app.requests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed %s",
        args=("GET",),
        exc_info=None,
    )
    record.event = "request_completed"
    record.request_id = "abc123"
    record.status = 200

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.requests"
    assert payload["message"] == "request_completed GET"
    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "abc123"
    assert payload["status"] == 200
    assert payload["timestamp"]


def test_json_formatter_keeps_the_traceback_of_a_failed_call() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.core.errors",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="provider failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_installs_the_configured_format() -> None:
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)

    try:
        configure_logging(Settings(log_format="json", log_level="DEBUG"))

        assert root.level == logging.DEBUG
        formatters = [
            handler.formatter
            for handler in root.handlers
            if isinstance(handler.formatter, JsonFormatter)
        ]
        assert formatters

        configure_logging(Settings(log_format="plain", log_level="INFO"))

        assert root.level == logging.INFO
        json_formatters = [
            handler.formatter
            for handler in root.handlers
            if isinstance(handler.formatter, JsonFormatter)
        ]
        assert not json_formatters
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)


# --- request middleware -----------------------------------------------------


def test_requests_are_logged_with_timing_and_a_request_id(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.requests"):
        response = client.get("/api/documents")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id

    record = next(
        record for record in caplog.records if record.name == "app.requests"
    )
    assert record.event == "request_completed"
    assert record.method == "GET"
    assert record.path == "/api/documents"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert record.request_id == request_id
    assert "request_completed" in record.getMessage()


def test_a_callers_request_id_is_echoed_back(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/documents", headers={"X-Request-ID": "corr-42.1"}
    )

    assert response.headers["X-Request-ID"] == "corr-42.1"


def test_an_unsafe_request_id_is_replaced_with_a_generated_one(
    client: TestClient,
) -> None:
    response = client.get("/api/documents", headers={"X-Request-ID": "bad id!"})

    echoed = response.headers["X-Request-ID"]
    assert echoed != "bad id!"
    assert len(echoed) == 32
    assert all(char in "0123456789abcdef" for char in echoed)


def test_health_polls_are_not_logged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr("app.api.routes.health.check_database", lambda: True)

    with caplog.at_level(logging.INFO, logger="app.requests"):
        response = client.get("/api/health")

    assert response.status_code == 200
    assert not [
        record for record in caplog.records if record.name == "app.requests"
    ]
