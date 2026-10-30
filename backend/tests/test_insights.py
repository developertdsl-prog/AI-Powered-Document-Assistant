"""Tests for summaries and structured extraction (Phase 4.2)."""

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
from app.models import Document, User
from app.services.insights import (
    EMPTY_DOCUMENT_SUMMARY,
    InsightFormatError,
    Passage,
    build_context,
    build_summary_messages,
    extract_insights,
    extractive_insights,
    extractive_summary,
    generate_summary,
    load_passages,
    parse_extraction,
)
from app.services.llm import LLMError
from tests.test_retrieval import add_chunk, ready_document

REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."
WAREHOUSE_SENTENCE = "Our warehouse operates Monday to Friday."
INVOICE_SENTENCE = "Acme Corp issued this on March 3, 2026."

# One fact per line so the offline "name: value" lookup stops at the line end.
INVOICE_TEXT = (
    f"{INVOICE_SENTENCE}\n"
    "The invoice number: INV-2024-015\n"
    "Due date: 2026-04-01\n"
    "Contact Jane Doe for questions."
)


def _passages(*contents: str, page: int | None = None) -> list[Passage]:
    return [
        Passage(
            chunk_id=uuid4(),
            chunk_index=index - 1,
            page_number=page,
            content=content,
        )
        for index, content in enumerate(contents, start=1)
    ]


# --- context assembly ------------------------------------------------------


def test_build_context_labels_passages_and_reports_no_truncation() -> None:
    context = build_context(_passages(REFUND_SENTENCE, WAREHOUSE_SENTENCE, page=2), budget=1000)

    assert context.text.startswith("[1] (page 2)\n")
    assert f"[2] (page 2)\n{WAREHOUSE_SENTENCE}" in context.text
    assert context.truncated is False
    assert len(context.passages) == 2


def test_build_context_cuts_at_the_budget_and_reports_it() -> None:
    long_passage = f"{REFUND_SENTENCE} " * 40

    context = build_context(_passages(long_passage, WAREHOUSE_SENTENCE), budget=200)

    assert context.truncated is True
    assert len(context.passages) == 1
    assert len(context.text) <= 200 + 16
    assert context.text.endswith("…")
    assert WAREHOUSE_SENTENCE not in context.text


def test_build_context_of_no_passages_is_empty_and_not_truncated() -> None:
    context = build_context([], budget=200)

    assert context.text == ""
    assert context.passages == []
    assert context.truncated is False


def test_load_passages_returns_chunks_in_reading_order(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    add_chunk(db_session, document, chunk_index=1, content=WAREHOUSE_SENTENCE, embedding=None)
    add_chunk(db_session, document, chunk_index=0, content=REFUND_SENTENCE, embedding=None)

    passages = load_passages(db_session, document_id=document.id)

    assert [passage.content for passage in passages] == [
        REFUND_SENTENCE,
        WAREHOUSE_SENTENCE,
    ]


# --- extractive summaries --------------------------------------------------


def test_concise_summary_quotes_the_opening_sentences() -> None:
    summary = extractive_summary(_passages(REFUND_SENTENCE, WAREHOUSE_SENTENCE), length="concise")

    # Concise stays within a few sentences, so both fit and stay in order.
    assert summary == f"{REFUND_SENTENCE} {WAREHOUSE_SENTENCE}"


def test_detailed_summary_is_longer_than_a_concise_one() -> None:
    passages = _passages(*[f"Sentence number {index} about the document." for index in range(10)])

    concise = extractive_summary(passages, length="concise")
    detailed = extractive_summary(passages, length="detailed")

    assert len(detailed) > len(concise)
    assert detailed.startswith(concise)


def test_summary_of_text_without_sentence_breaks_still_returns_text() -> None:
    summary = extractive_summary(_passages("no punctuation at all"), length="concise")

    assert summary == "no punctuation at all"


# --- summary prompts -------------------------------------------------------


def test_summary_prompt_labels_the_document_as_untrusted() -> None:
    context = build_context(_passages(REFUND_SENTENCE, page=3), budget=1000)

    messages = build_summary_messages(filename="terms.pdf", context=context, length="concise")

    assert [message["role"] for message in messages] == ["system", "user"]
    assert "untrusted" in messages[0]["content"]
    assert "Document: terms.pdf" in messages[1]["content"]
    assert "[1] (page 3)" in messages[1]["content"]
    assert REFUND_SENTENCE in messages[1]["content"]
    assert "one to three sentences" in messages[1]["content"]


# --- extraction parsing ----------------------------------------------------


def test_parse_extraction_reads_every_collection() -> None:
    raw = (
        '{"key_points": ["Refunds take 14 days"], "dates": ["2026-03-03"], '
        '"names": ["Acme Corp"], "fields": {"Invoice number": "INV-1"}}'
    )

    parsed = parse_extraction(raw, fields=["Invoice number"], max_items=10)

    assert parsed.key_points == ["Refunds take 14 days"]
    assert parsed.dates == ["2026-03-03"]
    assert parsed.names == ["Acme Corp"]
    assert parsed.field_values == {"Invoice number": "INV-1"}


def test_parse_extraction_tolerates_code_fences() -> None:
    raw = '```json\n{"key_points": ["Kept"], "dates": [], "names": []}\n```'

    parsed = parse_extraction(raw, fields=[], max_items=10)

    assert parsed.key_points == ["Kept"]


def test_parse_extraction_matches_requested_fields_case_insensitively() -> None:
    raw = '{"key_points": [], "dates": [], "names": [], "fields": {"INVOICE NUMBER": "INV-9"}}'

    parsed = parse_extraction(raw, fields=["Invoice number"], max_items=10)

    assert parsed.field_values == {"Invoice number": "INV-9"}


def test_parse_extraction_coerces_numeric_field_values() -> None:
    raw = '{"key_points": [], "dates": [], "names": [], "fields": {"Total": 42}}'

    parsed = parse_extraction(raw, fields=["Total"], max_items=10)

    assert parsed.field_values == {"Total": "42"}


def test_parse_extraction_rejects_text_that_is_not_json() -> None:
    with pytest.raises(InsightFormatError):
        parse_extraction("Sorry, here is what I found.", fields=[], max_items=10)


def test_parse_extraction_rejects_json_that_is_not_an_object() -> None:
    with pytest.raises(InsightFormatError):
        parse_extraction('["a list"]', fields=[], max_items=10)


def test_parse_extraction_rejects_a_collection_that_is_not_a_list() -> None:
    with pytest.raises(InsightFormatError):
        parse_extraction('{"key_points": "one point"}', fields=[], max_items=10)


def test_parse_extraction_drops_non_string_items_and_caps_the_list() -> None:
    raw = '{"key_points": ["kept", 7, "", "second", "third"], "dates": [], "names": []}'

    parsed = parse_extraction(raw, fields=[], max_items=2)

    assert parsed.key_points == ["kept", "second"]


def test_parse_extraction_drops_oversized_values_without_splitting_words() -> None:
    raw = json.dumps({"key_points": ["word " * 200], "dates": [], "names": []})

    parsed = parse_extraction(raw, fields=[], max_items=1)

    assert len(parsed.key_points[0]) <= 401
    assert not parsed.key_points[0].endswith(" ")


# --- extractive extraction -------------------------------------------------


def test_extractive_insights_finds_dates_names_and_fields() -> None:
    result = extractive_insights(
        _passages(INVOICE_TEXT),
        fields=["Invoice number", "Missing"],
        max_items=10,
    )

    assert "Acme Corp" in result.names
    assert "March 3, 2026" in result.dates
    assert "2026-04-01" in result.dates
    assert result.field_values == {"Invoice number": "INV-2024-015"}
    assert "Missing" not in result.field_values
    assert result.key_points[0] == INVOICE_SENTENCE


def test_extractive_insights_ignores_sentence_openers_as_names() -> None:
    result = extractive_insights(_passages("The board meets weekly."), fields=[], max_items=10)

    assert result.names == []


def test_extractive_insights_respects_the_item_limit() -> None:
    text = " ".join(f"Date {index} is 2026-03-0{index}." for index in range(1, 6))

    result = extractive_insights(_passages(text), fields=[], max_items=3)

    assert len(result.dates) == 3


# --- pipeline (service entry points) --------------------------------------


def _document_with_text(
    db: Session,
    user: User,
    settings: Settings,
    tmp_path: Path,
    *contents: str,
) -> Document:
    document = ready_document(db, user, settings, tmp_path)
    for index, content in enumerate(contents):
        add_chunk(db, document, chunk_index=index, content=content, embedding=None)
    return document


def test_generate_summary_quotes_the_document_offline(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(
        db_session, user, app_settings, tmp_path, REFUND_SENTENCE, WAREHOUSE_SENTENCE
    )

    result = generate_summary(
        db_session,
        document=document,
        length="concise",
        settings=app_settings,
    )

    assert REFUND_SENTENCE in result.summary
    assert result.provider == "extractive"
    assert result.source_chunks == 2
    assert result.truncated is False


def test_generate_summary_reports_a_document_without_text(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)

    result = generate_summary(
        db_session,
        document=document,
        length="concise",
        settings=app_settings,
    )

    assert result.summary == EMPTY_DOCUMENT_SUMMARY
    assert result.source_chunks == 0
    assert result.truncated is False


def test_generate_summary_flags_a_document_longer_than_the_budget(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(
        db_session,
        user,
        app_settings,
        tmp_path,
        f"{REFUND_SENTENCE} " * 40,
        WAREHOUSE_SENTENCE,
    )
    settings = app_settings.model_copy(update={"summary_max_context_chars": 200})

    result = generate_summary(
        db_session,
        document=document,
        length="concise",
        settings=settings,
    )

    assert result.truncated is True
    assert result.source_chunks == 1
    assert WAREHOUSE_SENTENCE not in result.summary


def test_generate_summary_calls_the_provider_with_the_prompt(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, REFUND_SENTENCE)

    class _RecordingChat:
        name = "openai"
        messages: list[dict[str, str]] = []

        def complete(self, messages: list[dict[str, str]]) -> str:
            self.messages = list(messages)
            return "  A model-written summary.  "

    chat = _RecordingChat()
    monkeypatch.setattr(
        "app.services.insights.get_chat_provider",
        lambda _settings: chat,
    )
    settings = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )

    result = generate_summary(
        db_session,
        document=document,
        length="detailed",
        settings=settings,
    )

    assert result.summary == "A model-written summary."
    assert result.provider == "openai"
    assert "untrusted" in chat.messages[0]["content"]
    assert "source.txt" in chat.messages[1]["content"]
    assert REFUND_SENTENCE in chat.messages[1]["content"]
    assert "several short paragraphs" in chat.messages[1]["content"]


def test_generate_summary_rejects_a_disabled_provider(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    settings = app_settings.model_copy(update={"llm_provider": "none"})

    with pytest.raises(AnswersUnavailableError):
        generate_summary(
            db_session,
            document=document,
            length="concise",
            settings=settings,
        )


def test_extract_insights_returns_found_and_missing_fields(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, INVOICE_TEXT)

    result = extract_insights(
        db_session,
        document=document,
        fields=["Invoice number", "Due date"],
        max_items=10,
        settings=app_settings,
    )

    assert result.provider == "extractive"
    assert "Acme Corp" in result.names
    assert "March 3, 2026" in result.dates
    by_name = {item.name: item for item in result.fields}
    assert by_name["Invoice number"].found is True
    assert by_name["Invoice number"].value == "INV-2024-015"
    assert by_name["Due date"].found is True
    assert by_name["Due date"].value is not None


def test_extract_insights_reports_a_document_without_text(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)

    result = extract_insights(
        db_session,
        document=document,
        fields=["Invoice number"],
        max_items=10,
        settings=app_settings,
    )

    assert result.key_points == []
    assert result.dates == []
    assert result.names == []
    assert result.fields[0].found is False
    assert result.fields[0].value is None


def test_extract_insights_rejects_a_reply_that_is_not_json(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, INVOICE_TEXT)

    class _BadChat:
        name = "openai"

        def complete(self, messages: list[dict[str, str]]) -> str:
            return "I could not extract anything."

    monkeypatch.setattr(
        "app.services.insights.get_chat_provider",
        lambda _settings: _BadChat(),
    )
    settings = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )

    with pytest.raises(InsightFormatError):
        extract_insights(
            db_session,
            document=document,
            fields=[],
            max_items=10,
            settings=settings,
        )


# --- API endpoints ---------------------------------------------------------


def _summary(
    client: TestClient,
    document: Document,
    payload: dict[str, object] | None = None,
) -> httpx.Response:
    return client.post(f"/api/documents/{document.id}/summaries", json=payload or {})


def _extraction(
    client: TestClient,
    document: Document,
    payload: dict[str, object] | None = None,
) -> httpx.Response:
    return client.post(f"/api/documents/{document.id}/extractions", json=payload or {})


def test_summaries_endpoint_returns_a_generated_summary(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(
        db_session, user, app_settings, tmp_path, REFUND_SENTENCE, WAREHOUSE_SENTENCE
    )

    response = _summary(client, document, {"length": "concise"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(document.id)
    assert payload["length"] == "concise"
    assert payload["provider"] == "extractive"
    assert payload["source_chunks"] == 2
    assert payload["truncated"] is False
    assert REFUND_SENTENCE in payload["summary"]
    assert payload["generated_at"]


def test_summaries_endpoint_defaults_to_a_concise_summary(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, REFUND_SENTENCE)

    response = _summary(client, document)

    assert response.status_code == 200
    assert response.json()["length"] == "concise"


def test_summaries_endpoint_rejects_an_unknown_length(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263/summaries",
        json={"length": "verbose"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_summaries_endpoint_rejects_unprocessed_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    document.status = "processing"
    db_session.commit()

    response = _summary(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_summaries_endpoint_hides_other_users_documents(
    client: TestClient,
    db_session: Session,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    owner = User(email="owner@example.com", full_name="Owner")
    db_session.add(owner)
    db_session.commit()
    document = ready_document(db_session, owner, app_settings, tmp_path)

    response = _summary(client, document)

    assert response.status_code == 404


def test_summaries_endpoint_reports_disabled_generation(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, REFUND_SENTENCE)
    disabled = app_settings.model_copy(update={"llm_provider": "none"})
    app.dependency_overrides[get_settings] = lambda: disabled

    response = _summary(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "answers_unavailable"


def test_summaries_endpoint_returns_503_when_the_provider_fails(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, REFUND_SENTENCE)

    def _fail(_settings: Settings) -> object:
        raise LLMError("provider is down")

    monkeypatch.setattr("app.services.insights.get_chat_provider", _fail)
    failing = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: failing

    response = _summary(client, document)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_extractions_endpoint_returns_collections_and_fields(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, INVOICE_TEXT)

    response = _extraction(
        client,
        document,
        {"fields": ["Invoice number", "Owner"], "max_items": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(document.id)
    assert payload["provider"] == "extractive"
    assert payload["truncated"] is False
    assert "Acme Corp" in payload["names"]
    assert "March 3, 2026" in payload["dates"]
    assert payload["key_points"][0] == INVOICE_SENTENCE
    assert payload["fields"] == [
        {"name": "Invoice number", "value": "INV-2024-015", "found": True},
        {"name": "Owner", "value": None, "found": False},
    ]


def test_extractions_endpoint_rejects_a_blank_field_name(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263/extractions",
        json={"fields": ["   "]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_extractions_endpoint_rejects_too_many_fields(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263/extractions",
        json={"fields": [f"field {index}" for index in range(11)]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_extractions_endpoint_rejects_unprocessed_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    document.status = "failed"
    db_session.commit()

    response = _extraction(client, document)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_extractions_endpoint_returns_503_for_an_invalid_reply(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document_with_text(db_session, user, app_settings, tmp_path, INVOICE_TEXT)

    class _BadChat:
        name = "openai"

        def complete(self, messages: list[dict[str, str]]) -> str:
            return "not json"

    monkeypatch.setattr(
        "app.services.insights.get_chat_provider",
        lambda _settings: _BadChat(),
    )
    failing = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: failing

    response = _extraction(client, document)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
