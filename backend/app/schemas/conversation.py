"""Conversation and message request and response schemas (Phase 4.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.answer import AnswerCitation, AnswerRequest

__all__ = [
    "AnswerRequest",
    "ConversationCreateRequest",
    "ConversationDetailResponse",
    "ConversationListResponse",
    "ConversationResponse",
    "MessageExchangeResponse",
    "MessageResponse",
]

DEFAULT_CONVERSATION_TITLE = "New conversation"
MAX_TITLE_LENGTH = 255


class ConversationCreateRequest(BaseModel):
    """Creates a conversation bound to one document."""

    document_id: UUID = Field(description="Document the conversation asks about.")
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="Optional title; defaults to the first question asked.",
    )

    @field_validator("title")
    @classmethod
    def _reject_blank_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("The title must not be blank.")
        return stripped


class ConversationResponse(BaseModel):
    """Public representation of one conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID | None
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Paginated conversation list, most recently updated first."""

    items: list[ConversationResponse]
    total: int


class MessageResponse(BaseModel):
    """One chat turn with the citations that back an assistant reply."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    position: int
    citations: list[AnswerCitation] = Field(default_factory=list)
    created_at: datetime

    @field_validator("citations", mode="before")
    @classmethod
    def _missing_citations_are_empty(cls, value: object) -> object:
        # User turns and legacy rows store no citations at all.
        return value or []


class ConversationDetailResponse(ConversationResponse):
    """A conversation with its message history in reading order."""

    messages: list[MessageResponse]


class MessageExchangeResponse(BaseModel):
    """The question and the grounded answer persisted for one request."""

    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
