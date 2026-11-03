"""AI usage and limits reporting (Phase 5.3)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.usage import (
    AiCallUsage,
    LimitsReport,
    RateLimitUsage,
    UsageResponse,
)
from app.services.usage import get_usage_tracker

router = APIRouter()


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="AI call usage and configured limits",
)
def usage_report(settings: Settings = Depends(get_settings)) -> UsageResponse:
    """Report per-process AI call counters next to the limits that bound them.

    The counters are informational: they answer "how much AI work did this
    process do, and how much of it failed" without keeping per-user data.
    """

    snapshot = get_usage_tracker().snapshot()

    return UsageResponse(
        reported_at=datetime.now(UTC),
        since=snapshot["since"],
        limits=LimitsReport(
            rate_limit=RateLimitUsage(
                enabled=settings.rate_limit_enabled,
                requests=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window_seconds,
            ),
            max_upload_size_bytes=settings.max_upload_size_bytes,
            answer_context_chunks=settings.answer_context_chunks,
            answer_max_context_chars=settings.answer_max_context_chars,
            summary_max_context_chars=settings.summary_max_context_chars,
            llm_max_tokens=settings.llm_max_tokens,
            provider_max_retries=settings.provider_max_retries,
        ),
        ai_calls=[
            AiCallUsage.model_validate(item) for item in snapshot["calls"]
        ],
    )
