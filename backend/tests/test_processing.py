"""Tests for the document processing pipeline."""

import shutil
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document, DocumentPage, User
from app.services.processing import process_document


def write_pdf(path: Path, page_texts: list[str]) -> None:
    pdf = pymupdf.open()

    try:
        for page_text in page_texts:
            page = pdf.new_page()
            page.insert_text((72, 72), page_text)
        pdf.save(path)
    finally:
        pdf.close()


def create_document(
    db: Session,
    user: User,
    settings: Settings,
    *,
    source: Path,
    filename: str,
    content_type: str,
) -> Document:
    relative_path = f"{user.id}/{filename}"
    destination = Path(settings.upload_dir) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)

    document = Document(
        owner_id=user.id,
        original_filename=filename,
        storage_path=relative_path,
        content_type=content_type,
        file_size_bytes=destination.stat().st_size,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@pytest.fixture
def stored_pdf(tmp_path: Path, db_session: Session) -> tuple[Document, Settings]:
    user = User(email="processor@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = Settings(
        upload_dir=str(tmp_path / "uploads"),
        process_uploads_in_background=False,
    )
    source = tmp_path / "source.pdf"
    write_pdf(source, ["First page", "Second page"])

    document = create_document(
        db_session,
        user,
        settings,
        source=source,
        filename="source.pdf",
        content_type="application/pdf",
    )
    return document, settings


def test_process_pdf_sets_ready_status_and_pages(
    db_session: Session,
    stored_pdf: tuple[Document, Settings],
) -> None:
    document, settings = stored_pdf

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "ready"
    assert processed.page_count == 2
    assert processed.error_message is None
    assert processed.processed_at is not None
    assert processed.doc_metadata is not None
    assert processed.doc_metadata["format"] == "pdf"

    pages = db_session.scalars(
        select(DocumentPage).order_by(DocumentPage.page_number)
    ).all()
    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].content == "First page"
    assert pages[0].character_count == len("First page")


def test_reprocessing_replaces_existing_pages(
    db_session: Session,
    stored_pdf: tuple[Document, Settings],
) -> None:
    document, settings = stored_pdf
    process_document(db_session, document.id, settings)
    process_document(db_session, document.id, settings)

    pages = db_session.scalars(select(DocumentPage)).all()
    assert len(pages) == 2


def test_corrupt_pdf_marks_document_failed(
    db_session: Session,
    stored_pdf: tuple[Document, Settings],
) -> None:
    document, settings = stored_pdf
    stored_path = Path(settings.upload_dir) / document.storage_path
    stored_path.write_bytes(b"not a valid pdf")

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "failed"
    assert processed.error_message is not None
    assert "PDF" in processed.error_message
    assert processed.page_count is None
    assert db_session.scalars(select(DocumentPage)).all() == []


def test_missing_file_marks_document_failed(
    db_session: Session,
    stored_pdf: tuple[Document, Settings],
) -> None:
    document, settings = stored_pdf
    stored_path = Path(settings.upload_dir) / document.storage_path
    stored_path.unlink()

    processed = process_document(db_session, document.id, settings)

    assert processed is not None
    assert processed.status == "failed"
    assert "missing" in (processed.error_message or "").lower()


def test_unknown_document_returns_none(
    db_session: Session,
    tmp_path: Path,
) -> None:
    from uuid import uuid4

    settings = Settings(upload_dir=str(tmp_path / "uploads"))

    assert process_document(db_session, uuid4(), settings) is None
