"""Integration tests for the initial database models."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Conversation,
    Document,
    DocumentChunk,
    DocumentPage,
    Message,
    User,
)


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    test_engine = create_engine("sqlite://")

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as db_session:
        yield db_session


def _create_document(session: Session, user: User) -> Document:
    document = Document(
        owner_id=user.id,
        original_filename="report.pdf",
        storage_path="uploads/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="ready",
        page_count=3,
    )
    session.add(document)
    session.flush()
    return document


def test_document_chunk_conversation_and_message_round_trip(
    session: Session,
) -> None:
    user = User(email="owner@example.com", full_name="Owner")
    session.add(user)
    session.flush()

    document = _create_document(session, user)
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="The quarterly revenue grew by 12 percent.",
        page_number=1,
        token_count=9,
    )
    page = DocumentPage(
        document_id=document.id,
        page_number=1,
        content="The quarterly revenue grew by 12 percent.",
        character_count=42,
        page_metadata={"width": 612.0},
    )
    conversation = Conversation(
        owner_id=user.id,
        document_id=document.id,
        title="Revenue question",
    )
    session.add_all([chunk, page, conversation])
    session.flush()

    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Revenue grew by 12 percent.",
        citations={"page": 1},
    )
    session.add(message)
    session.commit()

    stored_user = session.scalars(select(User)).one()
    stored_document = session.scalars(select(Document)).one()
    assert stored_user.documents == [stored_document]
    assert stored_document.chunks[0].content.startswith("The quarterly")
    assert stored_document.pages[0].content.startswith("The quarterly")
    assert session.scalars(select(Message)).one().role == "assistant"


def test_deleting_user_cascades_to_owned_records(session: Session) -> None:
    user = User(email="delete-me@example.com")
    session.add(user)
    session.flush()

    document = _create_document(session, user)
    session.add(
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="Chunk",
        )
    )
    session.add(
        DocumentPage(
            document_id=document.id,
            page_number=1,
            content="Page",
            character_count=4,
        )
    )
    conversation = Conversation(owner_id=user.id, document_id=document.id)
    session.add(conversation)
    session.flush()
    session.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content="Hello",
        )
    )
    session.commit()

    session.delete(user)
    session.commit()

    assert session.scalars(select(Document)).all() == []
    assert session.scalars(select(DocumentChunk)).all() == []
    assert session.scalars(select(DocumentPage)).all() == []
    assert session.scalars(select(Conversation)).all() == []
    assert session.scalars(select(Message)).all() == []


def test_duplicate_chunk_index_is_rejected(session: Session) -> None:
    user = User(email="chunks@example.com")
    session.add(user)
    session.flush()
    document = _create_document(session, user)

    session.add_all(
        [
            DocumentChunk(document_id=document.id, chunk_index=0, content="one"),
            DocumentChunk(document_id=document.id, chunk_index=0, content="two"),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_page_number_is_rejected(session: Session) -> None:
    user = User(email="pages@example.com")
    session.add(user)
    session.flush()
    document = _create_document(session, user)

    session.add_all(
        [
            DocumentPage(
                document_id=document.id,
                page_number=1,
                content="one",
                character_count=3,
            ),
            DocumentPage(
                document_id=document.id,
                page_number=1,
                content="two",
                character_count=3,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_document_status_is_rejected(session: Session) -> None:
    user = User(email="status@example.com")
    session.add(user)
    session.flush()

    session.add(
        Document(
            owner_id=user.id,
            original_filename="bad.pdf",
            storage_path="uploads/bad.pdf",
            content_type="application/pdf",
            file_size_bytes=10,
            status="not-a-status",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
