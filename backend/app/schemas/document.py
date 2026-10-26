"""Document request and response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Public representation of a stored document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    checksum: str | None
    status: str
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentResponse]
    total: int


class DocumentPageResponse(BaseModel):
    """Extracted text for one page."""

    page_number: int
    content: str
    character_count: int
    metadata: dict[str, Any] | None


class DocumentTextResponse(BaseModel):
    """Extracted text and processing metadata for a document."""

    document_id: UUID
    status: str
    page_count: int | None
    metadata: dict[str, Any] | None
    pages: list[DocumentPageResponse]
