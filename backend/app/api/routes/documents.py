"""Document upload, listing, detail, and extracted-text routes."""

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
from app.core.exceptions import DocumentNotReadyError
from app.db.session import get_db
from app.models import Document, User
from app.schemas.common import ErrorResponse
from app.schemas.document import (
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    DocumentTextResponse,
)
from app.services import documents as document_service
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """Return a paginated list of documents owned by the current user."""

    items, total = document_service.list_documents(
        db,
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
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
