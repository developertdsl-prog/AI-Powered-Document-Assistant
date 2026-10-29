"""Conversation history: ownership, persistence, and message ordering.

Conversations group a question and its grounded answer for one document
(Phase 4.1). The answer pipeline itself lives in
:mod:`app.services.answers`; this module only records turns:

- every lookup is scoped to the owner, so another user's conversation is
  indistinguishable from a missing one (``404``);
- messages are written one transaction at a time and ordered by an explicit
  per-conversation ``position``, because ``created_at`` is identical for a
  question and its reply;
- the first question becomes the conversation title unless one was given.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConversationNotFoundError
from app.models import Conversation, Document, Message
from app.schemas.answer import AnswerCitation
from app.schemas.conversation import (
    DEFAULT_CONVERSATION_TITLE,
    MAX_TITLE_LENGTH,
)
from app.services.answers import AnswerResult

DEFAULT_LIST_LIMIT = 50


def list_conversations(
    db: Session,
    *,
    owner_id: UUID,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> tuple[list[Conversation], int]:
    """Return the owner's conversations, most recently updated first."""

    total = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.owner_id == owner_id)
    ) or 0

    items = list(
        db.scalars(
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def create_conversation(
    db: Session,
    *,
    owner_id: UUID,
    document: Document,
    title: str | None = None,
) -> Conversation:
    """Create a conversation bound to an already-authorized document."""

    conversation = Conversation(
        owner_id=owner_id,
        document_id=document.id,
        title=(title or DEFAULT_CONVERSATION_TITLE)[:MAX_TITLE_LENGTH],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(
    db: Session,
    *,
    owner_id: UUID,
    conversation_id: UUID,
) -> Conversation:
    """Return one conversation owned by ``owner_id``, or raise ``404``."""

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_id == owner_id,
        )
    )
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


def list_messages(db: Session, conversation_id: UUID) -> list[Message]:
    """Return a conversation's messages in reading order."""

    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.position, Message.created_at, Message.id)
        ).all()
    )


def _next_position(db: Session, conversation_id: UUID) -> int:
    highest = db.scalar(
        select(func.max(Message.position)).where(
            Message.conversation_id == conversation_id
        )
    )
    return (highest or 0) + 1


def record_exchange(
    db: Session,
    *,
    conversation: Conversation,
    question: str,
    result: AnswerResult,
    settings: Settings,
) -> tuple[Message, Message]:
    """Persist the question and its answer as two ordered messages.

    Each message commits separately so ``created_at`` also advances for
    engines with second-resolution timestamps, while ``position`` keeps the
    order deterministic either way. The first question titles the
    conversation while it still carries the default title.
    """

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
        position=_next_position(db, conversation.id),
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        position=_next_position(db, conversation.id),
        citations=[
            AnswerCitation(
                reference=item.reference,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                page_number=item.page_number,
                score=item.score,
                excerpt=item.content[: settings.answer_excerpt_chars],
            ).model_dump(mode="json")
            for item in result.citations
        ],
    )
    db.add(assistant_message)

    if conversation.title == DEFAULT_CONVERSATION_TITLE:
        conversation.title = question[:MAX_TITLE_LENGTH]

    # The list endpoint orders by activity, so bump the timestamp on every
    # exchange instead of only when the title changed.
    conversation.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(assistant_message)
    db.refresh(conversation)
    return user_message, assistant_message
