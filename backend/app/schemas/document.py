"""Document request and response schemas."""

from datetime import datetime
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
