"""Document persistence operations."""

from __future__ import annotations

import uuid
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DocumentNotFoundError
from app.models import Document, DocumentPage
from app.services.storage import delete_stored_file, save_upload


def create_document(
    db: Session,
    *,
    owner_id: uuid.UUID,
    filename: str | None,
    file_obj: BinaryIO,
    settings: Settings,
) -> Document:
    """Validate, store, and register a new document for an owner."""

    stored = save_upload(file_obj, filename, owner_id, settings)

    document = Document(
        owner_id=owner_id,
        original_filename=stored.original_filename,
        storage_path=stored.relative_path,
        content_type=stored.content_type,
        file_size_bytes=stored.file_size_bytes,
        checksum=stored.checksum,
        status="pending",
    )
    db.add(document)

    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_stored_file(stored.relative_path, settings)
        raise

    db.refresh(document)
    return document


def list_documents(
    db: Session,
    *,
    owner_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Document], int]:
    """Return a page of documents owned by the current user."""

    owner_filter = Document.owner_id == owner_id
    total = db.scalar(
        select(func.count()).select_from(Document).where(owner_filter)
    )
    items = list(
        db.scalars(
            select(Document)
            .where(owner_filter)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )

    return items, int(total or 0)


def get_document(
    db: Session,
    *,
    owner_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    """Fetch one document scoped to its owner."""

    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
    )

    if document is None:
        raise DocumentNotFoundError()

    return document


def list_document_pages(
    db: Session,
    *,
    document_id: uuid.UUID,
) -> list[DocumentPage]:
    """Return extracted pages in page order."""

    return list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()
    )
