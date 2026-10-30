"""Tests for the conversation API (Phase 4.1)."""

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models import Conversation, Document, User
from app.services.embeddings import HashEmbeddingProvider
from app.services.llm import LLMError
from tests.test_retrieval import add_chunk, ready_document

QUESTION = "What is the refund policy?"
REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."


def chat_document(
    db: Session,
    user: User,
    settings: Settings,
    tmp_path: Path,
) -> Document:
    """A ready document with one embedded chunk so answers are grounded."""

    document = ready_document(db, user, settings, tmp_path)
    query_vector = HashEmbeddingProvider().embed_texts([QUESTION])[0]
    add_chunk(
        db,
        document,
        chunk_index=0,
        content=REFUND_SENTENCE,
        embedding=query_vector,
    )
    return document


def start_conversation(client: TestClient, document: Document, **body: object):
    response = client.post("/api/conversations", json={"document_id": str(document.id), **body})
    assert response.status_code == 201, response.text
    return response.json()


def ask(client: TestClient, conversation_id: str, question: str = QUESTION):
    return client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"question": question},
    )


# --- listing and creation -------------------------------------------------


def test_list_conversations_starts_empty(client: TestClient) -> None:
    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_create_conversation_binds_a_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)

    payload = start_conversation(client, document)

    assert payload["document_id"] == str(document.id)
    assert payload["title"] == "New conversation"
    assert payload["id"]


def test_create_conversation_keeps_a_supplied_title(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)

    payload = start_conversation(client, document, title="  Refund questions  ")

    assert payload["title"] == "Refund questions"


def test_create_conversation_hides_other_users_documents(
    client: TestClient,
    db_session: Session,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    owner = User(email="owner@example.com", full_name="Owner")
    db_session.add(owner)
    db_session.commit()
    document = chat_document(db_session, owner, app_settings, tmp_path)

    response = client.post("/api/conversations", json={"document_id": str(document.id)})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_create_conversation_rejects_an_unknown_document(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/conversations",
        json={"document_id": "9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263"},
    )

    assert response.status_code == 404


def test_create_conversation_rejects_a_blank_title(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)

    response = client.post(
        "/api/conversations",
        json={"document_id": str(document.id), "title": "   "},
    )

    assert response.status_code == 422


def test_list_conversations_orders_by_recent_activity(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    first = start_conversation(client, document, title="Older")
    second = start_conversation(client, document, title="Newer")

    # Force a deterministic gap: SQLite timestamps can tie within a second.
    older = db_session.get(Conversation, UUID(first["id"]))
    assert older is not None
    older.updated_at = older.updated_at.replace(year=older.updated_at.year - 1)
    db_session.commit()

    payload = client.get("/api/conversations").json()

    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [second["id"], first["id"]]


# --- history --------------------------------------------------------------


def test_get_conversation_returns_an_empty_history(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    response = client.get(f"/api/conversations/{conversation['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == conversation["id"]
    assert payload["messages"] == []


def test_history_keeps_question_then_answer_order(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    assert ask(client, conversation["id"]).status_code == 200
    assert ask(client, conversation["id"], "How long do refunds take?").status_code == 200

    payload = client.get(f"/api/conversations/{conversation['id']}").json()
    roles = [message["role"] for message in payload["messages"]]
    positions = [message["position"] for message in payload["messages"]]

    assert roles == ["user", "assistant", "user", "assistant"]
    assert positions == [1, 2, 3, 4]


def test_get_conversation_hides_other_users_conversations(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    # The client is authenticated as `user`, so the conversation belongs to
    # somebody else to prove the owner filter.
    document = chat_document(db_session, user, app_settings, tmp_path)
    other = User(email="other@example.com", full_name="Other")
    db_session.add(other)
    db_session.commit()
    conversation = Conversation(
        owner_id=other.id,
        document_id=document.id,
        title="Private thread",
    )
    db_session.add(conversation)
    db_session.commit()

    response = client.get(f"/api/conversations/{conversation.id}")

    assert response.status_code == 404


# --- asking questions -----------------------------------------------------


def test_ask_persists_the_question_and_a_grounded_answer(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    response = ask(client, conversation["id"])

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == conversation["id"]

    user_message = payload["user_message"]
    assert user_message["role"] == "user"
    assert user_message["content"] == QUESTION
    assert user_message["citations"] == []

    assistant_message = payload["assistant_message"]
    assert assistant_message["role"] == "assistant"
    assert REFUND_SENTENCE in assistant_message["content"]
    assert assistant_message["citations"]

    citation = assistant_message["citations"][0]
    assert citation["reference"] == 1
    assert citation["page_number"] is None
    assert citation["excerpt"].startswith("Refunds are issued")


def test_ask_titles_the_conversation_with_the_first_question(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    ask(client, conversation["id"])

    payload = client.get(f"/api/conversations/{conversation['id']}").json()
    assert payload["title"] == QUESTION


def test_ask_reports_disabled_answers(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)
    disabled = app_settings.model_copy(update={"llm_provider": "none"})
    app.dependency_overrides[get_settings] = lambda: disabled

    response = ask(client, conversation["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "answers_unavailable"


def test_ask_requires_a_ready_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)
    document.status = "pending"
    db_session.commit()

    response = ask(client, conversation["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_ask_rejects_a_conversation_without_a_document(
    client: TestClient,
    db_session: Session,
    user: User,
) -> None:
    conversation = Conversation(owner_id=user.id, document_id=None, title="Free chat")
    db_session.add(conversation)
    db_session.commit()

    response = ask(client, str(conversation.id))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_ask_hides_other_users_conversations(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    other = User(email="other@example.com", full_name="Other")
    db_session.add(other)
    db_session.commit()
    conversation = Conversation(
        owner_id=other.id,
        document_id=document.id,
        title="Private thread",
    )
    db_session.add(conversation)
    db_session.commit()

    response = ask(client, str(conversation.id))

    assert response.status_code == 404


def test_ask_rejects_a_blank_question(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    response = ask(client, conversation["id"], question="   ")

    assert response.status_code == 422


def test_failed_answer_is_not_persisted(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = chat_document(db_session, user, app_settings, tmp_path)
    conversation = start_conversation(client, document)

    def _fail(_settings: Settings) -> object:
        raise LLMError("provider is down")

    monkeypatch.setattr("app.services.answers.get_chat_provider", _fail)
    failing = app_settings.model_copy(
        update={"llm_provider": "openai", "openai_api_key": "test-key"}
    )
    app.dependency_overrides[get_settings] = lambda: failing

    response = ask(client, conversation["id"])

    assert response.status_code == 503
    detail = client.get(f"/api/conversations/{conversation['id']}").json()
    assert detail["messages"] == []
