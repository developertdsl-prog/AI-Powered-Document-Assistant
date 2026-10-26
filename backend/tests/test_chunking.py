"""Tests for the text chunking service."""

import dataclasses
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document, DocumentChunk, DocumentPage, User
from app.services.chunking import (
    ChunkingError,
    TextChunk,
    chunk_document,
    chunk_pages,
    estimate_tokens,
)
from app.services.extraction import ExtractedDocument, ExtractedPage
from app.services.processing import process_document
from tests.test_processing import create_document


def page(number: int, content: str) -> ExtractedPage:
    return ExtractedPage(page_number=number, content=content, metadata={})


def test_estimate_tokens_scales_with_length() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 8) == 2


def test_short_document_produces_single_chunk() -> None:
    chunks = chunk_pages([page(1, "One short paragraph.")])

    assert len(chunks) == 1
    assert chunks[0].content == "One short paragraph."
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].token_count == estimate_tokens("One short paragraph.")
    assert chunks[0].metadata["paragraph_count"] == 1
    assert chunks[0].metadata["spans_pages"] is False


def test_empty_pages_produce_no_chunks() -> None:
    assert chunk_pages([page(1, "")]) == []


def test_long_document_splits_into_multiple_chunks() -> None:
    paragraphs = [f"Paragraph {index} " + ("x" * 90) for index in range(10)]

    chunks = chunk_pages(
        [page(1, "\n\n".join(paragraphs))],
        chunk_size=300,
        chunk_overlap=50,
    )

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    joined = "\n\n".join(chunk.content for chunk in chunks)
    assert "Paragraph 0" in joined
    assert "Paragraph 9" in joined


def test_chunks_track_page_numbers() -> None:
    pages = [
        page(1, "First page content " + "a" * 200),
        page(2, "Second page content " + "b" * 200),
    ]

    chunks = chunk_pages(pages, chunk_size=250, chunk_overlap=50)

    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2
    tracked = {number for chunk in chunks for number in chunk.metadata["page_numbers"]}
    assert tracked == {1, 2}


def test_oversized_paragraph_is_hard_split() -> None:
    chunks = chunk_pages([page(1, "y" * 1500)], chunk_size=500, chunk_overlap=50)

    assert len(chunks) >= 3
    assert all(len(chunk.content) <= 500 for chunk in chunks)


def test_invalid_chunking_configuration_raises() -> None:
    with pytest.raises(ChunkingError):
        chunk_pages([page(1, "text")], chunk_size=0)

    with pytest.raises(ChunkingError):
        chunk_pages([page(1, "text")], chunk_size=100, chunk_overlap=100)


def test_chunk_document_uses_all_pages() -> None:
    document = ExtractedDocument(
        pages=[page(1, "Alpha"), page(2, "Beta")],
        metadata={},
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].content == "Alpha\n\nBeta"
    assert chunks[0].metadata["page_numbers"] == [1, 2]


@pytest.fixture
def stored_txt(tmp_path: Path, db_session: Session) -> tuple[Document, Settings]:
    user = User(email="chunker@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = Settings(
        upload_dir=str(tmp_path / "uploads"),
        process_uploads_in_background=False,
        chunk_size_chars=200,
        chunk_overlap_chars=40,
    )

    source = tmp_path / "source.txt"
    source.write_text(
        "\n\n".join(f"Section {index}: " + ("document text " * 20) for index in range(6)),
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


def test_processing_persists_chunks(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "ready"

    chunks = db_session.scalars(select(DocumentChunk).order_by(DocumentChunk.chunk_index)).all()
    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.token_count and chunk.token_count > 0 for chunk in chunks)
    assert all(chunk.page_number == 1 for chunk in chunks)

    pages = db_session.scalars(select(DocumentPage)).all()
    assert len(pages) == 1


def test_reprocessing_replaces_chunks(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt
    process_document(db_session, document.id, settings)
    first_count = len(db_session.scalars(select(DocumentChunk)).all())

    process_document(db_session, document.id, settings)

    chunks = db_session.scalars(select(DocumentChunk)).all()
    assert len(chunks) == first_count


def test_failed_processing_clears_chunks(
    db_session: Session,
    stored_txt: tuple[Document, Settings],
) -> None:
    document, settings = stored_txt
    process_document(db_session, document.id, settings)
    assert db_session.scalars(select(DocumentChunk)).all() != []

    stored_path = Path(settings.upload_dir) / document.storage_path
    stored_path.unlink()
    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "failed"
    assert db_session.scalars(select(DocumentChunk)).all() == []


def test_text_chunk_is_immutable() -> None:
    chunk = TextChunk(
        chunk_index=0,
        content="text",
        page_number=1,
        token_count=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.content = "changed"  # type: ignore[misc]
