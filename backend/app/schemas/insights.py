"""Summary and structured extraction request and response schemas (Phase 4.2)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SummaryLength = Literal["concise", "detailed"]

MAX_EXTRACTION_FIELDS = 10
MAX_FIELD_NAME_CHARS = 60


class SummaryRequest(BaseModel):
    """Options for summarizing one document."""

    length: SummaryLength = Field(
        default="concise",
        description="Concise is a few sentences, detailed covers the main ideas.",
    )


class SummaryResponse(BaseModel):
    """A generated summary of one document."""

    document_id: UUID
    length: SummaryLength
    summary: str
    provider: str
    source_chunks: int
    truncated: bool
    generated_at: datetime


class ExtractionRequest(BaseModel):
    """Options for extracting structured information from one document."""

    fields: list[str] = Field(
        default_factory=list,
        max_length=MAX_EXTRACTION_FIELDS,
        description="Custom field names to pull out of the document, in order.",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Maximum items returned per collection (key points, dates, names).",
    )

    @field_validator("fields")
    @classmethod
    def _normalize_fields(cls, values: list[str]) -> list[str]:
        """Trim, collapse whitespace, and drop duplicate field names."""

        cleaned: list[str] = []
        seen: set[str] = set()

        for value in values:
            name = " ".join(value.split())
            if not name:
                raise ValueError("Field names must not be blank.")
            if len(name) > MAX_FIELD_NAME_CHARS:
                raise ValueError(
                    f"Field names must be at most {MAX_FIELD_NAME_CHARS} characters."
                )
            if name.casefold() in seen:
                continue
            seen.add(name.casefold())
            cleaned.append(name)

        return cleaned


class ExtractedField(BaseModel):
    """One requested field and the value found for it, if any."""

    name: str
    value: str | None
    found: bool


class ExtractionResponse(BaseModel):
    """Key points, dates, names, and requested fields from one document."""

    document_id: UUID
    key_points: list[str]
    dates: list[str]
    names: list[str]
    fields: list[ExtractedField]
    provider: str
    source_chunks: int
    truncated: bool
    generated_at: datetime
