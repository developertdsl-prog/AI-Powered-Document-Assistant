"""Tests for the AI provider retry and timeout policy (Phase 5.3)."""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import EMBEDDING_DIMENSIONS, Settings, get_settings
from app.core.retry import is_retryable, request_with_retries
from app.main import app
from app.models import Document, User
from app.services.embeddings import (
    EmbeddingError,
    HashEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.services.llm import (
    LLMError,
    OpenAIChatProvider,
    get_chat_provider,
)
from tests.test_retrieval import add_chunk, ready_document

QUESTION = "What is the refund policy?"
REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."


def _response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, json={})


# --- retry helper -----------------------------------------------------------


def test_successful_request_is_not_retried() -> None:
    calls: list[int] = []
    delays: list[float] = []

    def send() -> httpx.Response:
        calls.append(1)
        return _response(200)

    response = request_with_retries(
        send, max_retries=3, backoff_seconds=0.5, sleep=delays.append
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert delays == []


def test_transient_status_is_retried_with_exponential_backoff() -> None:
    statuses = [503, 503, 200]
    delays: list[float] = []

    def send() -> httpx.Response:
        return _response(statuses.pop(0))

    response = request_with_retries(
        send, max_retries=2, backoff_seconds=0.5, sleep=delays.append
    )

    assert response.status_code == 200
    assert len(statuses) == 0
    assert delays == [0.5, 1.0]


def test_client_errors_are_returned_without_retrying() -> None:
    calls: list[int] = []
    delays: list[float] = []

    def send() -> httpx.Response:
        calls.append(1)
        return _response(400)

    response = request_with_retries(
        send, max_retries=3, backoff_seconds=0.5, sleep=delays.append
    )

    assert response.status_code == 400
    assert len(calls) == 1
    assert delays == []


def test_transport_errors_are_retried_then_raised() -> None:
    calls: list[int] = []
    delays: list[float] = []

    def send() -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(httpx.ConnectTimeout):
        request_with_retries(
            send, max_retries=2, backoff_seconds=0.25, sleep=delays.append
        )

    assert len(calls) == 3
    assert delays == [0.25, 0.5]


def test_retryable_status_is_returned_when_the_budget_runs_out() -> None:
    calls: list[int] = []

    def send() -> httpx.Response:
        calls.append(1)
        return _response(429)

    response = request_with_retries(send, max_retries=1, backoff_seconds=0)

    assert response.status_code == 429
    assert len(calls) == 2


def test_retryable_statuses_are_the_transient_ones() -> None:
    assert is_retryable(408)
    assert is_retryable(429)
    assert is_retryable(503)
    assert is_retryable(504)
    assert not is_retryable(400)
    assert not is_retryable(401)
    assert not is_retryable(404)


# --- chat provider ----------------------------------------------------------


def _chat_provider(
    handler: httpx.MockTransport,
    *,
    max_retries: int = 2,
) -> OpenAIChatProvider:
    return OpenAIChatProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1",
        max_retries=max_retries,
        retry_backoff_seconds=0,
        transport=handler,
    )


def test_chat_provider_retries_a_transient_status_then_succeeds() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return _response(503)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Recovered [1]."}}]}
        )

    provider = _chat_provider(httpx.MockTransport(handler), max_retries=2)

    reply = provider.complete([{"role": "user", "content": "Question?"}])

    assert reply == "Recovered [1]."
    assert len(calls) == 3


def test_chat_provider_does_not_retry_client_errors() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _response(400)

    provider = _chat_provider(httpx.MockTransport(handler))

    with pytest.raises(LLMError, match="HTTP 400"):
        provider.complete([{"role": "user", "content": "Question?"}])

    assert len(calls) == 1


def test_chat_provider_gives_up_after_the_retry_budget() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _response(503)

    provider = _chat_provider(httpx.MockTransport(handler), max_retries=1)

    with pytest.raises(LLMError, match="HTTP 503"):
        provider.complete([{"role": "user", "content": "Question?"}])

    assert len(calls) == 2


def test_chat_provider_retries_a_slow_response_then_succeeds() -> None:
    """A slow upstream surfaces as a read timeout that the budget absorbs."""

    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("upstream is slow")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Recovered [1]."}}]}
        )

    provider = _chat_provider(httpx.MockTransport(handler), max_retries=1)

    reply = provider.complete([{"role": "user", "content": "Question?"}])

    assert reply == "Recovered [1]."
    assert len(calls) == 2


def test_chat_provider_gives_up_when_every_attempt_times_out() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("upstream is slow")

    provider = _chat_provider(httpx.MockTransport(handler), max_retries=1)

    with pytest.raises(LLMError, match="could not be reached"):
        provider.complete([{"role": "user", "content": "Question?"}])

    assert len(calls) == 2


def test_chat_provider_is_built_from_the_retry_settings() -> None:
    settings = Settings(
        openai_api_key="test-key",
        llm_timeout_seconds=7.5,
        provider_max_retries=5,
        provider_retry_backoff_seconds=0.25,
    )

    provider = get_chat_provider(settings)

    # The constructor reads private state; the test asserts the settings
    # really reach the provider instead of being dropped on the way.
    assert isinstance(provider, OpenAIChatProvider)
    assert provider._max_retries == 5
    assert provider._retry_backoff == 0.25
    assert provider._timeout == 7.5


# --- embedding provider -----------------------------------------------------


def test_embedding_provider_retries_a_rate_limit_then_succeeds() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return _response(429)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.0] * EMBEDDING_DIMENSIONS}
                ]
            },
        )

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        max_retries=2,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    vectors = provider.embed_texts(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSIONS
    assert len(calls) == 2


def test_embedding_provider_gives_up_after_the_retry_budget() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _response(503)

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        max_retries=1,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError, match="HTTP 503"):
        provider.embed_texts(["hello"])

    assert len(calls) == 2


# --- API endpoint -----------------------------------------------------------


def test_answers_endpoint_reports_503_when_every_attempt_times_out(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated timeouts become one 503 instead of a hung request."""

    document: Document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )

    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("upstream is slow")

    provider = _chat_provider(httpx.MockTransport(handler), max_retries=1)
    monkeypatch.setattr(
        "app.services.answers.get_chat_provider", lambda _settings: provider
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
    assert response.json()["error"]["code"] == "service_unavailable"
    assert len(calls) == 2
