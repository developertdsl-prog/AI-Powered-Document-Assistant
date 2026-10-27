"""Application configuration loaded from environment variables."""

from functools import lru_cache

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
    dev_user_email: str = "dev@local.test"
    dev_user_name: str = "Development User"
    process_uploads_in_background: bool = True
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 150
    embedding_provider: str = "auto"
    embedding_batch_size: int = 100
    embedding_timeout_seconds: float = 30.0
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"

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
