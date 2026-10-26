"""Document processing pipeline: extract text and record status."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentChunk, DocumentPage
from app.services.chunking import ChunkingError, chunk_pages
from app.services.extraction import ExtractionError, extract_document

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 2000


def _extension_of(document: Document) -> str:
    return Path(document.original_filename).suffix.lower().lstrip(".")


def _mark_failed(
    db: Session,
    document_id: UUID,
    message: str,
) -> Document | None:
    document = db.get(Document, document_id)
    if document is None:
        return None

    db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    document.status = "failed"
    document.error_message = message[:MAX_ERROR_MESSAGE_LENGTH]
    document.page_count = None
    document.processed_at = datetime.now(UTC)
    db.commit()
    db.refresh(document)
    return document


def process_document(
    db: Session,
    document_id: UUID,
    settings: Settings,
) -> Document | None:
    """Extract text for one document and record the outcome.

    Returns the updated document, or ``None`` when the document no longer
    exists. Expected extraction problems are recorded on the document instead
    of being raised.
    """

    document = db.get(Document, document_id)
    if document is None:
        return None

    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        upload_root = Path(settings.upload_dir).resolve()
        stored_path = (upload_root / document.storage_path).resolve()

        if not stored_path.is_relative_to(upload_root):
            raise ExtractionError("The stored file path is invalid.")

        if not stored_path.is_file():
            raise ExtractionError("The stored file is missing.")

        extracted = extract_document(
            stored_path,
            _extension_of(document),
        )

        db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        for page in extracted.pages:
            db.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    content=page.content,
                    character_count=len(page.content),
                    page_metadata=page.metadata,
                )
            )

        chunks = chunk_pages(
            extracted.pages,
            chunk_size=settings.chunk_size_chars,
            chunk_overlap=settings.chunk_overlap_chars,
        )

        if not chunks:
            raise ChunkingError("No chunkable text was produced.")

        for chunk in chunks:
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                )
            )

        document.page_count = len(extracted.pages)
        document.doc_metadata = extracted.metadata
        document.status = "ready"
        document.error_message = None
        document.processed_at = datetime.now(UTC)
        db.commit()
        db.refresh(document)
        return document
    except (ExtractionError, ChunkingError) as exc:
        db.rollback()
        return _mark_failed(db, document_id, str(exc))
    except Exception:
        logger.exception("Unexpected error processing document %s", document_id)
        db.rollback()
        return _mark_failed(
            db,
            document_id,
            "The document could not be processed.",
        )


def process_document_in_background(document_id: UUID) -> None:
    """Run processing with its own session, after the upload response."""

    with SessionLocal() as db:
        process_document(db, document_id, get_settings())
