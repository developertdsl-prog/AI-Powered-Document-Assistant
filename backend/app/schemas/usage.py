"""AI usage and limits schemas (Phase 5.3)."""

from datetime import datetime

from pydantic import BaseModel, Field


class RateLimitUsage(BaseModel):
    """The per-user request limits currently in force."""

    enabled: bool
    requests: int
    window_seconds: int


class LimitsReport(BaseModel):
    """Configured resource limits that bound AI and upload work."""

    rate_limit: RateLimitUsage
    max_upload_size_bytes: int
    answer_context_chunks: int
    answer_max_context_chars: int
    summary_max_context_chars: int
    llm_max_tokens: int
    provider_max_retries: int


class AiCallUsage(BaseModel):
    """Counters for one operation and provider pair."""

    operation: str
    provider: str
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    total_duration_ms: float = Field(ge=0)
    average_duration_ms: float = Field(ge=0)


class UsageResponse(BaseModel):
    """AI call counters and the limits that bound them."""

    reported_at: datetime
    since: datetime
    limits: LimitsReport
    ai_calls: list[AiCallUsage]
