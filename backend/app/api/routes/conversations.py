"""Conversation list, creation, history, and question routes (Phase 4.1)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AnswerProviderError,
    ConversationWithoutDocumentError,
    DocumentNotReadyError,
)
from app.db.session import get_db
from app.models import Conversation, User
from app.schemas.answer import AnswerRequest
from app.schemas.common import ErrorResponse
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageExchangeResponse,
    MessageResponse,
)
from app.services import answers as answer_service
from app.services import conversations as conversation_service
from app.services import documents as document_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

_ERROR_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "The conversation is not linked to a document.",
    },
    404: {"model": ErrorResponse, "description": "Resource not found."},
    409: {
        "model": ErrorResponse,
        "description": (
            "The document has not finished processing, or answer generation "
            "is unavailable on this server."
        ),
    },
    503: {
        "model": ErrorResponse,
        "description": "The answer provider is unavailable.",
    },
}


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List the current user's conversations",
)
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    """Return a paginated list owned by the current user, newest first."""

    items, total = conversation_service.list_conversations(
        db,
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return ConversationListResponse(
        items=[ConversationResponse.model_validate(item) for item in items],
        total=total,
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation about a document",
    responses={404: {"model": ErrorResponse, "description": "Document not found."}},
)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    """Bind a new conversation to a document owned by the current user."""

    # Ownership is checked here: a foreign document is a 404 before any
    # conversation row is written.
    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=payload.document_id,
    )

    return conversation_service.create_conversation(
        db,
        owner_id=current_user.id,
        document=document,
        title=payload.title,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get a conversation with its message history",
    responses={404: {"model": ErrorResponse, "description": "Conversation not found."}},
)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailResponse:
    """Return one owned conversation and its messages in reading order."""

    conversation = conversation_service.get_conversation(
        db,
        owner_id=current_user.id,
        conversation_id=conversation_id,
    )
    messages = conversation_service.list_messages(db, conversation_id=conversation.id)

    return ConversationDetailResponse(
        **ConversationResponse.model_validate(conversation).model_dump(),
        messages=[MessageResponse.model_validate(message) for message in messages],
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageExchangeResponse,
    summary="Ask a question and receive a cited answer",
    responses=_ERROR_RESPONSES,
)
def create_message(
    conversation_id: UUID,
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MessageExchangeResponse:
    """Answer a question from the conversation's document and persist both turns.

    The answer uses the same grounded pipeline as
    ``POST /api/documents/{id}/answers``; nothing is guessed from outside the
    retrieved passages.
    """

    conversation = conversation_service.get_conversation(
        db,
        owner_id=current_user.id,
        conversation_id=conversation_id,
    )

    if conversation.document_id is None:
        raise ConversationWithoutDocumentError()

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=conversation.document_id,
    )

    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    try:
        result = answer_service.answer_question(
            db,
            document=document,
            question=payload.question,
            settings=settings,
            limit=payload.limit,
        )
    except answer_service.LLMError as exc:
        raise AnswerProviderError() from exc

    user_message, assistant_message = conversation_service.record_exchange(
        db,
        conversation=conversation,
        question=payload.question,
        result=result,
        settings=settings,
    )

    return MessageExchangeResponse(
        conversation_id=conversation.id,
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )
