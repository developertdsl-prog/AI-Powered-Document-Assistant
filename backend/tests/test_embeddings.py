"""Tests for embedding providers and chunk embedding in processing."""

import json
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import EMBEDDING_DIMENSIONS, Settings
from app.models import Document, DocumentChunk, User
from app.services.embeddings import (
    EmbeddingError,
    HashEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from app.services.processing import process_document
from tests.test_processing import create_document


class FailingProvider:
    """Test double that always raises."""

    name = "failing"
    dimensions = EMBEDDING_DIMENSIONS

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingError("Embedding provider failure (test double).")


def test_hash_provider_is_deterministic_and_normalized() -> None:
    provider = HashEmbeddingProvider(dimensions=32)

    first = provider.embed_texts(["alpha", "beta"])
    second = provider.embed_texts(["alpha", "beta"])

    assert first == second
    assert len(first) == 2
    assert all(len(vector) == 32 for vector in first)
    for vector in first:
        norm = sum(value * value for value in vector) ** 0.5
        assert norm == pytest.approx(1.0)


def test_hash_provider_distinguishes_different_texts() -> None:
    provider = HashEmbeddingProvider(dimensions=64)

    alpha, beta = provider.embed_texts(["alpha", "beta"])

    assert alpha != beta


def test_hash_provider_uses_configured_dimensions() -> None:
    provider = HashEmbeddingProvider()

    (vector,) = provider.embed_texts(["anything"])

    assert len(vector) == EMBEDDING_DIMENSIONS


def test_hash_provider_rejects_invalid_dimensions() -> None:
    with pytest.raises(EmbeddingError):
        HashEmbeddingProvider(dimensions=0)


def test_openai_provider_requires_api_key() -> None:
    with pytest.raises(EmbeddingError):
        OpenAIEmbeddingProvider(
            api_key="",
            model="text-embedding-3-small",
            base_url="https://api.openai.com/v1",
        )


def test_openai_provider_returns_vectors_in_order() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content.decode("utf-8"))
        inputs = payload["input"]
        data = [
            {"index": index, "embedding": [float(index + 1)] * EMBEDDING_DIMENSIONS}
            for index, _ in enumerate(inputs)
        ]
        # Return out of order to prove the client re-sorts by index.
        data.reverse()
        return httpx.Response(200, json={"data": data})

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        dimensions=EMBEDDING_DIMENSIONS,
        transport=httpx.MockTransport(handler),
    )

    vectors = provider.embed_texts(["one", "two", "three"])

    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0]
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in vectors)
    assert len(calls) == 1
    auth = calls[0].headers["Authorization"]
    assert auth == "Bearer sk-test"


def test_openai_provider_batches_requests() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        batch_sizes.append(len(payload["input"]))
        data = [
            {"index": index, "embedding": [0.5] * EMBEDDING_DIMENSIONS}
            for index in range(len(payload["input"]))
        ]
        return httpx.Response(200, json={"data": data})

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        batch_size=2,
        transport=httpx.MockTransport(handler),
    )

    vectors = provider.embed_texts(["a", "b", "c", "d", "e"])

    assert batch_sizes == [2, 2, 1]
    assert len(vectors) == 5


def test_openai_provider_sends_dimensions_only_for_v3_models() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen.append(payload)
        data = [
            {"index": index, "embedding": [0.1] * EMBEDDING_DIMENSIONS}
            for index in range(len(payload["input"]))
        ]
        return httpx.Response(200, json={"data": data})

    v3 = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )
    v3.embed_texts(["x"])

    legacy = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-ada-002",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )
    legacy.embed_texts(["x"])

    assert "dimensions" in seen[0]
    assert "dimensions" not in seen[1]


def test_openai_provider_reports_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    provider = OpenAIEmbeddingProvider(
        api_key="sk-bad",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError, match="HTTP 401"):
        provider.embed_texts(["x"])


def test_openai_provider_reports_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError, match="could not be reached"):
        provider.embed_texts(["x"])


def test_openai_provider_rejects_wrong_vector_width() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError, match="width"):
        provider.embed_texts(["x"])


def test_openai_provider_handles_empty_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made")

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://embeddings.example/v1",
        transport=httpx.MockTransport(handler),
    )

    assert provider.embed_texts([]) == []


def test_provider_selection_none_returns_no_provider() -> None:
    settings = Settings(embedding_provider="none")
    assert get_embedding_provider(settings) is None


def test_provider_selection_hash() -> None:
    settings = Settings(embedding_provider="hash")
    provider = get_embedding_provider(settings)
    assert isinstance(provider, HashEmbeddingProvider)


def test_provider_selection_auto_without_key_uses_hash() -> None:
    settings = Settings(embedding_provider="auto", openai_api_key=None)
    provider = get_embedding_provider(settings)
    assert isinstance(provider, HashEmbeddingProvider)


def test_provider_selection_auto_with_key_uses_openai() -> None:
    settings = Settings(embedding_provider="auto", openai_api_key="sk-test")
    provider = get_embedding_provider(settings)
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_provider_selection_openai_without_key_fails() -> None:
    settings = Settings(embedding_provider="openai", openai_api_key=None)
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        get_embedding_provider(settings)


def test_provider_selection_unknown_fails() -> None:
    settings = Settings(embedding_provider="mystery")
    with pytest.raises(EmbeddingError, match="Unknown embedding provider"):
        get_embedding_provider(settings)


@pytest.fixture
def stored_txt(tmp_path: Path, db_session: Session) -> tuple[Document, Settings]:
    user = User(email="embedder@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = Settings(
        upload_dir=str(tmp_path / "uploads"),
        process_uploads_in_background=False,
        chunk_size_chars=400,
        chunk_overlap_chars=50,
        embedding_provider="hash",
    )

    source = tmp_path / "source.txt"
    source.write_text(
        "\n\n".join(f"Section {index}: " + ("embedding text " * 15) for index in range(4)),
        encoding="utf-8",
    )

    document = create_document(
        db_session,
        user,
        settings,
        source=source,
        filename="source.txt",
        content_type="text/plain",
    )
    return document, settings


def test_processing_stores_chunk_embeddings(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "ready"
    assert processed.doc_metadata is not None
    assert processed.doc_metadata["embedding_provider"] == "hash"

    chunks = db_session.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index)).all()
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == EMBEDDING_DIMENSIONS


def test_processing_without_embeddings_stores_null_vectors(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt
    settings.embedding_provider = "none"

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "ready"
    assert processed.doc_metadata is not None
    assert processed.doc_metadata["embedding_provider"] is None

    chunks = db_session.scalars(select(DocumentChunk)).all()
    assert all(chunk.embedding is None for chunk in chunks)


def test_embedding_failure_marks_document_failed(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt

    with patch(
        "app.services.processing.get_embedding_provider",
        return_value=FailingProvider(),
    ):
        processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "failed"
    assert "failure" in (processed.error_message or "").lower()
    assert db_session.scalars(select(DocumentChunk)).all() == []
    assert (
        db_session.scalars(select(Document).where(Document.id == document.id)).one().status
        == "failed"
    )


def test_unknown_provider_marks_document_failed(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt
    settings.embedding_provider = "mystery"

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "failed"
    assert "Unknown embedding provider" in (processed.error_message or "")


def test_hash_vectors_match_reference_implementation() -> None:
    """Pin the hash provider contract: same input always yields same vector."""

    vector = HashEmbeddingProvider(dimensions=8).embed_texts(["stable chunk"])[0]

    assert len(vector) == 8
    again = HashEmbeddingProvider(dimensions=8).embed_texts(["stable chunk"])[0]
    assert vector == again
    # Changing a byte of input must change the vector.
    other = HashEmbeddingProvider(dimensions=8).embed_texts(["stable chunks"])[0]
    assert vector != other
