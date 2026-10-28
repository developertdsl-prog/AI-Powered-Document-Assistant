"""Tests for similarity search over embedded document chunks."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document, DocumentChunk, User
from app.services.embeddings import HashEmbeddingProvider
from app.services.retrieval import (
    RetrievalError,
    cosine_similarity,
    search_document_chunks,
)
from tests.test_processing import create_document


def ready_document(
    db: Session,
    user: User,
    settings: Settings,
    tmp_path: Path,
) -> Document:
    source = tmp_path / "source.txt"
    source.write_text("Retrieval source text.", encoding="utf-8")

    document = create_document(
        db,
        user,
        settings,
        source=source,
        filename="source.txt",
        content_type="text/plain",
    )
    document.status = "ready"
    db.commit()
    db.refresh(document)
    return document


def add_chunk(
    db: Session,
    document: Document,
    *,
    chunk_index: int,
    content: str,
    embedding: list[float] | None,
) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=chunk_index,
        content=content,
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()
    return chunk


def test_cosine_similarity_scores_identical_vectors_as_one() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_scores_opposite_vectors_as_minus_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_scores_orthogonal_vectors_as_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_rejects_mismatched_widths() -> None:
    with pytest.raises(RetrievalError):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_search_returns_the_closest_chunk_first(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    provider = HashEmbeddingProvider(dimensions=64)
    query_vector = provider.embed_texts(["refund policy"])[0]

    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content="Unrelated introduction.",
        embedding=[-value for value in query_vector],
    )
    expected = add_chunk(
        db_session,
        document,
        chunk_index=1,
        content="Refunds are issued within 14 days.",
        embedding=query_vector,
    )

    results = search_document_chunks(
        db_session,
        document_id=document.id,
        query_vector=query_vector,
        limit=5,
    )

    assert len(results) == 2
    assert results[0][0].id == expected.id
    assert results[0][1] == pytest.approx(1.0)


def test_search_skips_chunks_without_embeddings(
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
        content="Stored without a vector.",
        embedding=None,
    )
    add_chunk(
        db_session,
        document,
        chunk_index=1,
        content="Stored with a vector.",
        embedding=[1.0, 0.0],
    )

    results = search_document_chunks(
        db_session,
        document_id=document.id,
        query_vector=[1.0, 0.0],
        limit=5,
    )

    assert [chunk.chunk_index for chunk, _score in results] == [1]


def test_search_respects_the_result_limit(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    for chunk_index in range(4):
        add_chunk(
            db_session,
            document,
            chunk_index=chunk_index,
            content=f"Chunk {chunk_index}.",
            embedding=[1.0, 0.0],
        )

    results = search_document_chunks(
        db_session,
        document_id=document.id,
        query_vector=[1.0, 0.0],
        limit=2,
    )

    assert len(results) == 2


def test_search_rejects_a_non_positive_limit(
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)

    with pytest.raises(RetrievalError):
        search_document_chunks(
            db_session,
            document_id=document.id,
            query_vector=[1.0, 0.0],
            limit=0,
        )


def test_search_endpoint_ranks_chunks_for_a_query(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    provider = HashEmbeddingProvider()
    query_vector = provider.embed_texts(["refund policy"])[0]

    add_chunk(
        db_session,
        document,
        chunk_index=0,
        content="Refunds are issued within 14 days.",
        embedding=query_vector,
    )
    add_chunk(
        db_session,
        document,
        chunk_index=1,
        content="Shipping takes three to five days.",
        embedding=[-value for value in query_vector],
    )

    response = client.post(
        f"/api/documents/{document.id}/search",
        json={"query": "refund policy", "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(document.id)
    assert len(payload["results"]) == 1
    assert payload["results"][0]["chunk_index"] == 0
    assert payload["results"][0]["score"] == pytest.approx(1.0)


def test_search_endpoint_rejects_unprocessed_document(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    document = ready_document(db_session, user, app_settings, tmp_path)
    document.status = "pending"
    db_session.commit()

    response = client.post(
        f"/api/documents/{document.id}/search",
        json={"query": "refund policy"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_ready"


def test_search_endpoint_hides_other_users_documents(
    client: TestClient,
    db_session: Session,
    user: User,
    app_settings: Settings,
    tmp_path: Path,
) -> None:
    owner = User(email="owner@example.com", full_name="Owner")
    db_session.add(owner)
    db_session.commit()

    document = ready_document(db_session, owner, app_settings, tmp_path)

    response = client.post(
        f"/api/documents/{document.id}/search",
        json={"query": "refund policy"},
    )

    assert response.status_code == 404


def test_search_endpoint_rejects_a_blank_query(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/documents/9f9d7f23-0f4d-4fd0-b6f0-2d9f3ab90263/search",
        json={"query": "   "},
    )

    assert response.status_code == 422
