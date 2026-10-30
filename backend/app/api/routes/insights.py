"""Summary and structured extraction routes (Phase 4.2)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import DocumentNotReadyError, InsightProviderError
from app.db.session import get_db
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.insights import (
    ExtractedField,
    ExtractionRequest,
    ExtractionResponse,
    SummaryRequest,
    SummaryResponse,
)
from app.services import documents as document_service
from app.services import insights as insight_service
from app.services.insights import InsightFormatError
from app.services.llm import LLMError

router = APIRouter(prefix="/documents", tags=["insights"])

_INSIGHT_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Document not found."},
    409: {
        "model": ErrorResponse,
        "description": (
            "Document has not finished processing, or generation "
            "is unavailable on this server."
        ),
    },
    503: {
        "model": ErrorResponse,
        "description": "The summary provider is unavailable or returned an invalid reply.",
    },
}


@router.post(
    "/{document_id}/summaries",
    response_model=SummaryResponse,
    summary="Generate a summary",
    responses=_INSIGHT_ERROR_RESPONSES,
)
def generate_document_summary(
    document_id: UUID,
    payload: SummaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SummaryResponse:
    """Summarize a ready document in reading order.

    The summary covers the passages that fit the context budget; ``truncated``
    is true when the document was longer than that.
    """

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )

    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    try:
        result = insight_service.generate_summary(
            db,
            document=document,
            length=payload.length,
            settings=settings,
        )
    except (LLMError, InsightFormatError) as exc:
        raise InsightProviderError() from exc

    return SummaryResponse(
        document_id=document.id,
        length=payload.length,
        summary=result.summary,
        provider=result.provider,
        source_chunks=result.source_chunks,
        truncated=result.truncated,
        generated_at=datetime.now(UTC),
    )


@router.post(
    "/{document_id}/extractions",
    response_model=ExtractionResponse,
    summary="Extract structured information",
    responses=_INSIGHT_ERROR_RESPONSES,
)
def extract_document_insights(
    document_id: UUID,
    payload: ExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ExtractionResponse:
    """Extract key points, dates, names, and requested fields.

    Custom field names come back with ``found`` false and no value when the
    document does not contain them.
    """

    document = document_service.get_document(
        db,
        owner_id=current_user.id,
        document_id=document_id,
    )

    if document.status != "ready":
        raise DocumentNotReadyError(document.status)

    try:
        result = insight_service.extract_insights(
            db,
            document=document,
            fields=payload.fields,
            max_items=payload.max_items,
            settings=settings,
        )
    except (LLMError, InsightFormatError) as exc:
        raise InsightProviderError() from exc

    return ExtractionResponse(
        document_id=document.id,
        key_points=result.key_points,
        dates=result.dates,
        names=result.names,
        fields=[
            ExtractedField(name=item.name, value=item.value, found=item.found)
            for item in result.fields
        ],
        provider=result.provider,
        source_chunks=result.source_chunks,
        truncated=result.truncated,
        generated_at=datetime.now(UTC),
    )
