"""Document upload, listing, and detail routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Document, User
from app.schemas.common import ErrorResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services import documents as document_service

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
    file: UploadFile = File(..., description="PDF, DOCX, or TXT file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Document:
    """Validate, store, and register an uploaded document."""

    return document_service.create_document(
        db,
        owner_id=current_user.id,
        filename=file.filename,
        file_obj=file.file,
        settings=settings,
    )


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
