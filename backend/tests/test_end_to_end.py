"""End-to-end journey through the public API (Phase 5.2).

One account signs up, uploads, processes, searches, answers, chats,
summarizes, extracts, and deletes; a second account then repeats the
reads against those records to prove nothing crosses the ownership
boundary.
"""

from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.processing import process_document
from tests.test_auth import auth_header, login, register

HEADLINE = "Acme Corporation returns and shipping notes"
REFUND_SENTENCE = "Refunds are issued within 14 days of purchase."
SHIP_SENTENCE = "Orders ship within three business days."
SUPPORT_LINE = "Support lead: Ada Lovelace"
SIGNED_LINE = "Signed on 2026-03-04."

# Long enough to span several chunks while staying inside the1 MB test
# upload limit.
_FILLER = (
    "Customers may return unopened items in the original packaging. "
    "Opened items are reviewed case by case by the support team. "
) * 8

DOCUMENT_TEXT = (
    f"{HEADLINE}\n"
    "\n"
    f"{REFUND_SENTENCE}\n"
    f"{SHIP_SENTENCE}\n"
    "\n"
    f"{_FILLER}"
    "\n"
    "\n"
    f"{SUPPORT_LINE}\n"
    f"{SIGNED_LINE}\n"
)

QUESTION = "What is the refund policy?"


def _sign_in(client: TestClient, email: str) -> str:
    """Register an account and return a bearer token for it."""

    registered = register(client, email=email)
    assert registered.status_code == 201, registered.text
    signin = login(client, email=email)
    assert signin.status_code == 200, signin.text
    return signin.json()["access_token"]


def _upload(
    client: TestClient,
    token: str,
    *,
    filename: str = "policy.txt",
) -> httpx.Response:
    return client.post(
        "/api/documents",
        headers=auth_header(token),
        files={"file": (filename, DOCUMENT_TEXT.encode("utf-8"), "text/plain")},
    )


def test_full_document_journey_end_to_end(
    auth_client: TestClient,
    db_session: Session,
    app_settings: Settings,
) -> None:
    token = _sign_in(auth_client, "journey@example.com")

    # Upload leaves the document pending; processing flips it to ready.
    upload = _upload(auth_client, token)
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])
    assert upload.json()["status"] == "pending"

    processed = process_document(db_session, document_id, app_settings)
    assert processed is not None
    assert processed.status == "ready"

    # The library lists exactly the uploaded document.
    listed = auth_client.get("/api/documents", headers=auth_header(token)).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == str(document_id)
    assert listed["items"][0]["page_count"] == 1

    # Search ranks every chunk of the document for a query.
    search = auth_client.post(
        f"/api/documents/{document_id}/search",
        headers=auth_header(token),
        json={"query": "refund policy", "limit": 5},
    )
    assert search.status_code == 200, search.text
    results = search.json()["results"]
    assert len(results) >= 2
    assert any(REFUND_SENTENCE in item["content"] for item in results)
    scores = [item["score"] for item in results]
    assert scores == sorted(scores, reverse=True)

    # The answer is grounded in the document and cites the passage.
    answer = auth_client.post(
        f"/api/documents/{document_id}/answers",
        headers=auth_header(token),
        json={"question": QUESTION},
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert payload["grounded"] is True
    assert payload["provider"] == "extractive"
    assert payload["answer"] == REFUND_SENTENCE
    assert REFUND_SENTENCE in payload["citations"][0]["excerpt"]

    # Chat keeps the exchange and its citation in the conversation.
    conversation = auth_client.post(
        "/api/conversations",
        headers=auth_header(token),
        json={"document_id": str(document_id)},
    )
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]

    exchange = auth_client.post(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth_header(token),
        json={"question": QUESTION},
    )
    assert exchange.status_code == 200, exchange.text
    assistant = exchange.json()["assistant_message"]
    assert REFUND_SENTENCE in assistant["content"]
    assert assistant["citations"]

    history = auth_client.get(
        f"/api/conversations/{conversation_id}",
        headers=auth_header(token),
    ).json()
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]

    # Summaries quote the document; extractions read its fields.
    summary = auth_client.post(
        f"/api/documents/{document_id}/summaries",
        headers=auth_header(token),
        json={"length": "concise"},
    )
    assert summary.status_code == 200, summary.text
    assert REFUND_SENTENCE in summary.json()["summary"]

    extraction = auth_client.post(
        f"/api/documents/{document_id}/extractions",
        headers=auth_header(token),
        json={"fields": ["support lead", "budget"]},
    )
    assert extraction.status_code == 200, extraction.text
    insights = extraction.json()
    assert "2026-03-04" in insights["dates"]
    fields = {item["name"]: item for item in insights["fields"]}
    assert fields["support lead"]["found"] is True
    assert fields["support lead"]["value"] == "Ada Lovelace"
    assert fields["budget"]["found"] is False

    # Deleting removes it from the library for its owner.
    deleted = auth_client.delete(
        f"/api/documents/{document_id}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 200
    after = auth_client.get("/api/documents", headers=auth_header(token)).json()
    assert after == {"items": [], "total": 0}


def test_a_second_account_never_sees_the_first_owners_records(
    auth_client: TestClient,
    db_session: Session,
    app_settings: Settings,
) -> None:
    owner_token = _sign_in(auth_client, "owner@example.com")
    upload = _upload(auth_client, owner_token, filename="private.txt")
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    assert process_document(db_session, UUID(document_id), app_settings) is not None

    conversation = auth_client.post(
        "/api/conversations",
        headers=auth_header(owner_token),
        json={"document_id": document_id},
    )
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]

    stranger_token = _sign_in(auth_client, "stranger@example.com")

    # The stranger's library starts empty.
    stranger_list = auth_client.get(
        "/api/documents",
        headers=auth_header(stranger_token),
    ).json()
    assert stranger_list == {"items": [], "total": 0}

    # Every document-scoped read answers 404 for someone else's document.
    detail = auth_client.get(
        f"/api/documents/{document_id}",
        headers=auth_header(stranger_token),
    )
    assert detail.status_code == 404

    text = auth_client.get(
        f"/api/documents/{document_id}/text",
        headers=auth_header(stranger_token),
    )
    assert text.status_code == 404

    answers = auth_client.post(
        f"/api/documents/{document_id}/answers",
        headers=auth_header(stranger_token),
        json={"question": QUESTION},
    )
    assert answers.status_code == 404

    search = auth_client.post(
        f"/api/documents/{document_id}/search",
        headers=auth_header(stranger_token),
        json={"query": "refund"},
    )
    assert search.status_code == 404

    summary = auth_client.post(
        f"/api/documents/{document_id}/summaries",
        headers=auth_header(stranger_token),
        json={},
    )
    assert summary.status_code == 404

    # Conversations that mention the document stay closed too.
    stranger_conversation = auth_client.post(
        "/api/conversations",
        headers=auth_header(stranger_token),
        json={"document_id": document_id},
    )
    assert stranger_conversation.status_code == 404

    stranger_history = auth_client.get(
        f"/api/conversations/{conversation_id}",
        headers=auth_header(stranger_token),
    )
    assert stranger_history.status_code == 404

    stranger_message = auth_client.post(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth_header(stranger_token),
        json={"question": QUESTION},
    )
    assert stranger_message.status_code == 404

    delete = auth_client.delete(
        f"/api/documents/{document_id}",
        headers=auth_header(stranger_token),
    )
    assert delete.status_code == 404

    # The owner still sees everything after the stranger's attempts.
    owner_detail = auth_client.get(
        f"/api/documents/{document_id}",
        headers=auth_header(owner_token),
    )
    assert owner_detail.status_code == 200

    owner_history = auth_client.get(
        f"/api/conversations/{conversation_id}",
        headers=auth_header(owner_token),
    )
    assert owner_history.status_code == 200
