"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed embedding width shared by the model, the Alembic migration, and the
# embedding providers. Changing it is a schema change: add a new migration
# and update every provider together.
EMBEDDING_DIMENSIONS = 1536


class Settings(BaseSettings):
    """Runtime settings.

    Values are read from environment variables first and fall back to the
    optional ``.env`` file in the backend working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI-Powered Document Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api"
    # Structured logging: "plain" lines for development consoles, "json"
    # for log collectors in production.
    log_level: str = "INFO"
    log_format: Literal["plain", "json"] = "plain"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5433/ai_document_assistant"
    )
    db_echo: bool = False
    db_pool_pre_ping: bool = True
    db_connect_timeout_seconds: int = 5
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    allowed_file_types: list[str] = ["pdf", "docx", "txt"]
    # Secret for signing JWTs. The default is fine for local development;
    # production deployments must set their own so tokens cannot be forged.
    jwt_secret_key: str = "dev-only-secret-change-me-please-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Per-user limits for the expensive endpoints (uploads, answers,
    # messages, summaries, extractions). Counters use fixed windows and live
    # in process memory, which is fine for one backend process and noted for
    # Phase 6.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    process_uploads_in_background: bool = True
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 150
    embedding_provider: str = "auto"
    embedding_batch_size: int = 100
    embedding_timeout_seconds: float = 30.0
    # Shared retry budget for the HTTP AI providers (chat and embeddings):
    # transient failures (timeout, 429, 5xx) are retried with exponential
    # backoff before the API reports 503.
    provider_max_retries: int = 2
    provider_retry_backoff_seconds: float = 0.5
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    llm_provider: str = "auto"
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 700
    llm_timeout_seconds: float = 60.0
    answer_context_chunks: int = 6
    answer_min_similarity: float = 0.0
    answer_max_context_chars: int = 8000
    answer_excerpt_chars: int = 300
    # Summaries and extraction read the document in order instead of
    # retrieving, so they get their own, larger budget for long documents.
    summary_max_context_chars: int = 12000

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}

    @property
    def max_upload_size_bytes(self) -> int:
        return max(1, self.max_upload_size_mb) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""

    return Settings()
