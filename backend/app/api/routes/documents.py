"""Document upload, listing, detail, extracted-text, and answer routes."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AnswerProviderError,
    DocumentNotReadyError,
    EmbeddingsUnavailableError,
)
from app.db.session import get_db
from app.models import Document, User
from app.schemas.answer import AnswerCitation, AnswerRequest, AnswerResponse
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.document import (
    ChunkSearchRequest,
    ChunkSearchResponse,
    ChunkSearchResult,
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    DocumentTextResponse,
)
from app.services import answers as answer_service
from app.services import documents as document_service
from app.services import retrieval as retrieval_service
from app.services.embeddings import get_embedding_provider
from app.services.processing import process_document_in_background

router = APIRouter(prefix="/documents", tags=["documents"])

_UPLOAD_ERROR_RESPONSES = {
    413: {"model": ErrorResponse, "description": "File exceeds the size limit."},
    415: {"model": ErrorResponse, "description": "Unsupported or invalid file type."},
    422: {"model": ErrorResponse, "description": "Missing or empty file."},
}


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    responses=_UPLOAD_ERROR_RESPONSES,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX, or TXT file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Document:
    """Validate, store, and register an uploaded document."""

    document = document_service.create_document(
        db,
        owner_id=current_user.id,
        filename=file.filename,
        file_obj=file.file,
        settings=settings,
    )

    if settings.process_uploads_in_background:
        background_tasks.add_task(
            process_document_in_background,
            document.id,
        )

    return document


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List the current user's documents",
)
def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(
        default=None,
        max_length=200,
        description="Case-insensitive substring the filename must contain.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """Return a paginated list of documents owned by the current user."""

    items, total = document_service.list_documents(
        db,
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
        query=q,
    )

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document",
    responses={404: {"model": ErrorResponse, "description": "Document not found."}},
)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    """Return one document owned by the current user."""

    return document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete a document",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found."},
    },
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    """Delete a document together with its stored file and derived records.

    Pages, chunks, conversations, and messages are removed with it, so a
    failed upload can be cleaned up as easily as a ready one.
    """

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )

    document_service.delete_document(db, document=document, settings=settings)

    return MessageResponse(message="Document deleted.")


@router.get(
    "/{document_id}/text",
    response_model=DocumentTextResponse,
    summary="Get extracted text",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found."},
        409: {
            "model": ErrorResponse,
            "description": "Document has not finished processing.",
        },
    },
)
def get_document_text(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentTextResponse:
    """Return extracted text and metadata for a ready document."""

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )

    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    pages = document_service.list_document_pages(
        db,
        document_id=document.id,
    )

    return DocumentTextResponse(
        document_id=document.id,
        status=document.status,
        page_count=document.page_count,
        metadata=document.doc_metadata,
        pages=[
            DocumentPageResponse(
                page_number=page.page_number,
                content=page.content,
                character_count=page.character_count,
                metadata=page.page_metadata,
            )
            for page in pages
        ],
    )


@router.post(
    "/{document_id}/search",
    response_model=ChunkSearchResponse,
    summary="Search a document's chunks",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found."},
        409: {
            "model": ErrorResponse,
            "description": (
                "Document has not finished processing, or embeddings "
                "are disabled."
            ),
        },
    },
)
def search_document_chunks(
    document_id: UUID,
    payload: ChunkSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ChunkSearchResponse:
    """Embed the query and rank the document's chunks by cosine similarity."""

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )

    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    provider = get_embedding_provider(settings)
    if provider is None:
        raise EmbeddingsUnavailableError()

    (query_vector,) = provider.embed_texts([payload.query])

    matches = retrieval_service.search_document_chunks(
        db,
        document_id=document.id,
        query_vector=query_vector,
        limit=payload.limit,
    )

    return ChunkSearchResponse(
        document_id=document.id,
        query=payload.query,
        results=[
            ChunkSearchResult(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                score=score,
                content=chunk.content,
            )
            for chunk, score in matches
        ],
    )


_ANSWER_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Document not found."},
    409: {
        "model": ErrorResponse,
        "description": (
            "Document has not finished processing, or answer generation "
            "is unavailable on this server."
        ),
    },
    503: {
        "model": ErrorResponse,
        "description": "The answer provider is unavailable.",
    },
}


@router.post(
    "/{document_id}/answers",
    response_model=AnswerResponse,
    summary="Answer a question about a document",
    responses=_ANSWER_ERROR_RESPONSES,
)
def answer_document_question(
    document_id: UUID,
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AnswerResponse:
    """Retrieve evidence for the question and answer from it only.

    The reply cites the passages it used; ``grounded`` is true when at least
    one passage really supports the answer, and false for refusals.
    """

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
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

    return AnswerResponse(
        document_id=document.id,
        question=payload.question,
        answer=result.answer,
        grounded=result.grounded,
        citations=[
            AnswerCitation(
                reference=item.reference,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                page_number=item.page_number,
                score=item.score,
                excerpt=item.content[: settings.answer_excerpt_chars],
            )
            for item in result.citations
        ],
        provider=result.provider,
        evidence_count=result.evidence_count,
        generated_at=datetime.now(UTC),
    )
