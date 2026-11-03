"""Tests for AI usage counters and the usage endpoint (Phase 5.3)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models import User
from app.services.embeddings import HashEmbeddingProvider
from app.services.llm import LLMError
from app.services.usage import get_usage_tracker, record_ai_call
from tests.test_retrieval import add_chunk, ready_document

QUESTION = "What is the refund policy?"
REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."


@pytest.fixture(autouse=True)
def fresh_tracker() -> None:
    """Start each test with an empty, predictable counter table."""

    get_usage_tracker().reset()


def test_usage_endpoint_is_public_and_starts_empty(
    auth_client: TestClient,
    app_settings: Settings,
) -> None:
    response = auth_client.get("/api/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_calls"] == []
    assert body["reported_at"]
    assert body["since"]
    assert body["limits"] == {
        "rate_limit": {
            "enabled": app_settings.rate_limit_enabled,
            "requests": app_settings.rate_limit_requests,
            "window_seconds": app_settings.rate_limit_window_seconds,
        },
        "max_upload_size_bytes": app_settings.max_upload_size_bytes,
        "answer_context_chunks": app_settings.answer_context_chunks,
        "answer_max_context_chars": app_settings.answer_max_context_chars,
        "summary_max_context_chars": app_settings.summary_max_context_chars,
        "llm_max_tokens": app_settings.llm_max_tokens,
        "provider_max_retries": app_settings.provider_max_retries,
    }


def test_summary_calls_are_counted_per_operation_and_provider(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=HashEmbeddingProvider().embed_texts([REFUND_SENTENCE])[0],
    )

    response = client.post(
        f"/api/documents/{document.id}/summaries",
        json={"length": "concise"},
    )
    assert response.status_code == 200, response.text

    body = client.get("/api/usage").json()
    calls = {(item["operation"], item["provider"]): item for item in body["ai_calls"]}
    summary = calls[("summary", "extractive")]
    assert summary["total"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["total_duration_ms"] >= 0
    assert summary["average_duration_ms"] >= 0


def test_answer_failures_are_counted_as_well(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=HashEmbeddingProvider().embed_texts([QUESTION])[0],
    )

    class _FailingChat:
        name = "openai"

        def complete(self, messages: list[dict[str, str]]) -> str:
            raise LLMError("provider is down")

    monkeypatch.setattr(
        "app.services.answers.get_chat_provider",
        lambda _settings: _FailingChat(),
    )
    failing = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: failing

    response = client.post(
        f"/api/documents/{document.id}/answers",
        json={"question": QUESTION},
    )
    assert response.status_code == 503

    body = client.get("/api/usage").json()
    calls = {(item["operation"], item["provider"]): item for item in body["ai_calls"]}
    answer = calls[("answer", "openai")]
    assert answer["total"] == 1
    assert answer["failed"] == 1
    assert answer["succeeded"] == 0


def test_record_ai_call_counts_successes_and_failures() -> None:
    tracker = get_usage_tracker()

    with record_ai_call("answer", "extractive"):
        pass
    with pytest.raises(RuntimeError):
        with record_ai_call("answer", "extractive"):
            raise RuntimeError("boom")

    body = tracker.snapshot()
    (call,) = body["calls"]
    assert call["operation"] == "answer"
    assert call["provider"] == "extractive"
    assert call["total"] == 2
    assert call["succeeded"] == 1
    assert call["failed"] == 1
    assert call["total_duration_ms"] >= 0
    assert call["average_duration_ms"] >= 0
