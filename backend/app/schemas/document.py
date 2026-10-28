"""Document request and response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ChunkSearchRequest(BaseModel):
    """Natural language query used to rank a document's chunks."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Question or search phrase to match against the chunks.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of chunks to return.",
    )

    @field_validator("query")
    @classmethod
    def _reject_blank_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("The query must not be blank.")
        return stripped


class ChunkSearchResult(BaseModel):
    """One retrieved chunk with its similarity score."""

    chunk_id: UUID
    chunk_index: int
    page_number: int | None
    score: float
    content: str


class ChunkSearchResponse(BaseModel):
    """Ranked chunk matches for a document query."""

    document_id: UUID
    query: str
    results: list[ChunkSearchResult]
