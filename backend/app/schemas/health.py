"""Health-check schemas."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    database: Literal["up", "down"]
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
