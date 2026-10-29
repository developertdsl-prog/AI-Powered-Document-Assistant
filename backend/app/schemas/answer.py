"""Grounded answer request and response schemas (Phase 3.4)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AnswerRequest(BaseModel):
    """Question asked about one document."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Natural language question to answer from the document.",
    )
    limit: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Maximum number of passages retrieved as evidence.",
    )

    @field_validator("question")
    @classmethod
    def _reject_blank_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("The question must not be blank.")
        return stripped


class AnswerCitation(BaseModel):
    """One document passage referenced by an answer."""

    reference: int
    chunk_id: UUID
    chunk_index: int
    page_number: int | None
    score: float
    excerpt: str


class AnswerResponse(BaseModel):
    """A grounded answer with the passages that support it."""

    document_id: UUID
    question: str
    answer: str
    grounded: bool
    citations: list[AnswerCitation]
    provider: str
    evidence_count: int
    generated_at: datetime
