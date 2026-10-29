"""Tests for grounded answer generation (Phase 3.4)."""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AnswersUnavailableError
from app.main import app
from app.models import Document, DocumentChunk, User
from app.services.answers import (
    REFUSAL_ANSWER,
    AnswerResult,
    Evidence,
    build_evidence,
    build_messages,
    extractive_answer,
    generate_answer,
    get_answer_mode,
    parse_citations,
)
from app.services.embeddings import HashEmbeddingProvider
from app.services.llm import LLMError, OpenAIChatProvider, get_chat_provider
from tests.test_retrieval import add_chunk, ready_document

QUESTION = "What is the refund policy?"
REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."


# --- provider selection ---------------------------------------------------


def test_auto_mode_uses_the_offline_provider_without_an_api_key() -> None:
    settings = Settings(llm_provider="auto", openai_api_key=None)

    assert get_answer_mode(settings) == "extractive"


def test_auto_mode_prefers_the_openai_provider_when_a_key_is_set() -> None:
    settings = Settings(llm_provider="auto", openai_api_key="test-key")

    assert get_answer_mode(settings) == "openai"


def test_openai_mode_requires_an_api_key() -> None:
    settings = Settings(llm_provider="openai", openai_api_key=None)

    with pytest.raises(LLMError):
        get_answer_mode(settings)


def test_none_mode_disables_answers() -> None:
    settings = Settings(llm_provider="none")

    assert get_answer_mode(settings) is None


def test_unknown_mode_is_rejected() -> None:
    settings = Settings(llm_provider="magic")

    with pytest.raises(LLMError):
        get_answer_mode(settings)


# --- prompt assembly ------------------------------------------------------


def _evidence(*contents: str, page: int | None = None) -> list[Evidence]:
    return [
        Evidence(
            reference=index,
            chunk_id=uuid4(),
            chunk_index=index - 1,
            page_number=page,
            score=0.9,
            content=content,
        )
        for index, content in enumerate(contents, start=1)
    ]


def test_prompt_labels_the_document_as_untrusted_and_numbers_passages() -> None:
    settings = Settings(answer_max_context_chars=10_000)
    evidence = _evidence(REFUND_SENTENCE, "Shipping takes three days.", page=2)

    messages = build_messages(
        QUESTION,
        filename="terms.pdf",
        evidence=evidence,
        settings=settings,
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    assert "untrusted" in messages[0]["content"]
    assert REFUSAL_ANSWER in messages[0]["content"]

    user_message = messages[1]["content"]
    assert "Document: terms.pdf" in user_message
    assert f"[1] (page 2)\n{REFUND_SENTENCE}" in user_message
    assert "[2] (page 2)" in user_message
    assert QUESTION in user_message


def test_prompt_stays_within_the_context_budget() -> None:
    settings = Settings(answer_max_context_chars=200)
    long_passage = "Refund requests are handled by the support team. " * 20
    evidence = _evidence(long_passage, long_passage)

    messages = build_messages(
        QUESTION,
        filename="terms.pdf",
        evidence=evidence,
        settings=settings,
    )

    passages = messages[1]["content"].split("Passages:\n", 1)[1]
    context = passages.split("\n\nQuestion:", 1)[0]
    # The passage body, labels included, must fit inside the configured cap.
    assert len(context) <= settings.answer_max_context_chars + 16
    assert context.endswith("…")


# --- citations and extractive answers -------------------------------------


def test_citations_keep_only_supplied_references_and_drop_duplicates() -> None:
    evidence = _evidence(REFUND_SENTENCE, "Shipping takes three days.")

    assert parse_citations("It says [1], again [1], and [9].", evidence) == [1]


def test_citations_are_absent_when_the_model_invents_references() -> None:
    evidence = _evidence(REFUND_SENTENCE)

    assert parse_citations("Because [7] says so.", evidence) == []


def test_extractive_answer_quotes_the_overlapping_sentence() -> None:
    evidence = _evidence(
        REFUND_SENTENCE,
        "Our warehouse operates Monday to Friday.",
    )

    answer, citations = extractive_answer(QUESTION, evidence)

    assert answer == REFUND_SENTENCE
    assert citations == [1]


def test_extractive_answer_refuses_when_nothing_matches() -> None:
    evidence = _evidence("Our warehouse operates Monday to Friday.")

    answer, citations = extractive_answer("Tell me about gorilla migrations", evidence)

    assert answer == REFUSAL_ANSWER
    assert citations == []


def test_build_evidence_numbers_matches_in_rank_order() -> None:
    best = DocumentChunk(
        document_id=uuid4(),
        chunk_index=4,
        content="Best match.",
        page_number=2,
    )
    weaker = DocumentChunk(
        document_id=uuid4(),
        chunk_index=5,
        content="Weaker match.",
        page_number=3,
    )

    evidence = build_evidence([(best, 0.9), (weaker, 0.4)])

    assert [item.reference for item in evidence] == [1, 2]
    assert [item.chunk_index for item in evidence] == [4, 5]
    assert [item.page_number for item in evidence] == [2, 3]
    assert [item.score for item in evidence] == [0.9, 0.4]


def test_build_evidence_can_drop_weak_matches() -> None:
    chunk = DocumentChunk(
        document_id=uuid4(),
        chunk_index=0,
        content="Barely related.",
    )

    assert build_evidence([(chunk, 0.1)], min_similarity=0.5) == []


# --- answer pipeline ------------------------------------------------------


def test_generate_answer_grounds_the_extractive_reply(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    chunk = add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )

    result = generate_answer(
        db_session,
        document=document,
        question=QUESTION,
        query_vector=query_vector,
        settings=app_settings,
    )

    assert isinstance(result, AnswerResult)
    assert result.grounded is True
    assert result.provider == "extractive"
    assert result.evidence_count == 1
    assert [citation.chunk_id for citation in result.citations] == [chunk.id]
    assert REFUND_SENTENCE in result.answer


def test_generate_answer_refuses_when_the_document_has_no_evidence(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]

    result = generate_answer(
        db_session,
        document=document,
        question=QUESTION,
        query_vector=query_vector,
        settings=app_settings,
    )

    assert result.answer == REFUSAL_ANSWER
    assert result.grounded is False
    assert result.citations == []
    assert result.evidence_count == 0


def test_generate_answer_rejects_a_disabled_provider(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    settings = app_settings.model_copy(update={"llm_provider": "none"})
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]

    with pytest.raises(AnswersUnavailableError):
        generate_answer(
            db_session,
            document=document,
            question=QUESTION,
            query_vector=query_vector,
            settings=settings,
        )


class _RecordingChat:
    name = "openai"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.messages = list(messages)
        return self.reply


def test_generate_answer_calls_the_chat_provider_with_the_prompt(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )
    chat = _RecordingChat("Refunds take 14 days [1]")
    monkeypatch.setattr(
        "app.services.answers.get_chat_provider",
        lambda _settings: chat,
    )
    settings = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )

    result = generate_answer(
        db_session,
        document=document,
        question=QUESTION,
        query_vector=query_vector,
        settings=settings,
    )

    assert result.grounded is True
    assert result.provider == "openai"
    assert [citation.reference for citation in result.citations] == [1]
    assert "untrusted" in chat.messages[0]["content"]
    assert REFUND_SENTENCE in chat.messages[1]["content"]
    assert QUESTION in chat.messages[1]["content"]


def test_generate_answer_marks_invented_citations_as_not_grounded(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )
    monkeypatch.setattr(
        "app.services.answers.get_chat_provider",
        lambda _settings: _RecordingChat("An answer that cites [42]."),
    )
    settings = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )

    result = generate_answer(
        db_session,
        document=document,
        question=QUESTION,
        query_vector=query_vector,
        settings=settings,
    )

    assert result.grounded is False
    assert result.citations == []


# --- chat transport -------------------------------------------------------


def test_openai_chat_provider_posts_messages_and_returns_the_reply() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  Grounded reply.  "}}]},
        )

    provider = OpenAIChatProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )

    reply = provider.complete(
        [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Question?"},
        ]
    )

    assert reply == "Grounded reply."
    assert seen["path"] == "/v1/chat/completions"
    assert seen["authorization"] == "Bearer test-key"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert len(body["messages"]) == 2  # type: ignore[arg-type]


def test_openai_chat_provider_raises_on_an_http_error() -> None:
    provider = OpenAIChatProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, json={})
        ),
    )

    with pytest.raises(LLMError):
        provider.complete([{"role": "user", "content": "Question?"}])


def test_openai_chat_provider_raises_on_an_empty_answer() -> None:
    provider = OpenAIChatProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": "   "}}]}
            )
        ),
    )

    with pytest.raises(LLMError):
        provider.complete([{"role": "user", "content": "Question?"}])


def test_chat_provider_requires_an_api_key() -> None:
    settings = Settings(openai_api_key=None)

    with pytest.raises(LLMError):
        get_chat_provider(settings)


# --- API endpoint ---------------------------------------------------------


def _answer(
    client: TestClient,
    document: Document,
    question: str = QUESTION,
) -> httpx.Response:
    return client.post(
        f"/api/documents/{document.id}/answers",
        json={"question": question},
    )


def test_answers_endpoint_returns_a_grounded_answer(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )
    add_chunk(
        db_session,
        document,
        chunk_index=1,
        content="Our warehouse operates Monday to Friday.",
        embedding=[-value for value in query_vector],
    )

    response = _answer(client, document)

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(document.id)
    assert payload["question"] == QUESTION
    assert payload["grounded"] is True
    assert payload["provider"] == "extractive"
    assert payload["evidence_count"] == 2
    assert REFUND_SENTENCE in payload["answer"]
    assert len(payload["citations"]) == 1

    citation = payload["citations"][0]
    assert citation["reference"] == 1
    assert citation["chunk_index"] == 0
    assert citation["excerpt"].startswith("Refunds are issued")


def test_answers_endpoint_refuses_without_supporting_evidence(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)

    response = _answer(client, document)

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == REFUSAL_ANSWER
    assert payload["grounded"] is False
    assert payload["citations"] == []
    assert payload["evidence_count"] == 0


def test_answers_endpoint_rejects_unprocessed_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    document.status = "processing"
    db_session.commit()

    response = _answer(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_answers_endpoint_hides_other_users_documents(
    client: TestClient,
    db_session: Session,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    owner = User(email="owner@example.com", full_name="Owner")
    db_session.add(owner)
    db_session.commit()
    document = ready_document(db_session, owner, app_settings, tmp_path)

    response = _answer(client, document)

    assert response.status_code == 404


def test_answers_endpoint_rejects_a_blank_question(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263/answers",
        json={"question": "   "},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_answers_endpoint_reports_disabled_answers(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    disabled = app_settings.model_copy(update={"llm_provider": "none"})
    app.dependency_overrides[get_settings] = lambda: disabled

    response = _answer(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "answers_unavailable"


def test_answers_endpoint_reports_disabled_embeddings(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    no_embeddings = app_settings.model_copy(update={"embedding_provider": "none"})
    app.dependency_overrides[get_settings] = lambda: no_embeddings

    response = _answer(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "embeddings_unavailable"


def test_answers_endpoint_returns_503_when_the_provider_fails(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )

    def _fail(_settings: Settings) -> object:
        raise LLMError("provider is down")

    monkeypatch.setattr("app.services.answers.get_chat_provider", _fail)
    failing = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: failing

    response = _answer(client, document)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
