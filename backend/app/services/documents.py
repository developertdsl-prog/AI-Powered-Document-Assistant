"""Document persistence operations."""

from __future__ import annotations

import uuid
from typing import BinaryIO

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DocumentNotFoundError
from app.models import Conversation, Document, DocumentChunk, DocumentPage, Message
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


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards so a query for ``50%`` matches that filename."""

    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_documents(
    db: Session,
    *,
    owner_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
) -> tuple[list[Document], int]:
    """Return a page of documents owned by the current user.

    ``query`` optionally narrows the page to filenames containing it,
    case-insensitively; the count reflects the same filter so pagination and
    totals stay consistent.
    """

    filters = [Document.owner_id == owner_id]

    cleaned = (query or "").strip()
    if cleaned:
        # SQLite and PostgreSQL both fold case in lower(), and the escaped
        # pattern is matched literally in either one.
        filters.append(
            func.lower(Document.original_filename).like(
                f"%{_escape_like(cleaned).lower()}%",
                escape="\\",
            )
        )

    total = db.scalar(
        select(func.count()).select_from(Document).where(*filters)
    )
    items = list(
        db.scalars(
            select(Document)
            .where(*filters)
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


def delete_document(
    db: Session,
    *,
    document: Document,
    settings: Settings,
) -> None:
    """Delete a document, its stored file, and everything derived from it.

    The stored file goes first: a wasted file only costs disk space, while a
    row whose file is already gone could never be cleaned up again. Derived
    rows are deleted explicitly, the way ``_mark_failed`` does it: the
    relationships are ``passive_deletes``, which leaves the cascade to the
    database, and SQLite (the test database) only enforces it behind a
    ``PRAGMA`` that is not set. Explicit deletes behave identically on
    SQLite and PostgreSQL.

    Deleting during background processing is allowed: the task re-reads the
    document and stops when it is gone, and one already past that check only
    fails on the missing row, which rolls back without corrupting anything.
    """

    delete_stored_file(document.storage_path, settings)

    db.execute(
        delete(Message).where(
            Message.conversation_id.in_(
                select(Conversation.id).where(
                    Conversation.document_id == document.id
                )
            )
        )
    )
    db.execute(
        delete(Conversation).where(Conversation.document_id == document.id)
    )
    db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    db.commit()
