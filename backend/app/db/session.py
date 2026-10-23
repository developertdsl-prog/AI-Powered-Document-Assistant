"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _create_engine():
    settings = get_settings()
    url = make_url(settings.database_url)
    connect_args: dict[str, object] = {}

    if url.get_backend_name().startswith("postgresql"):
        connect_args["connect_timeout"] = settings.db_connect_timeout_seconds

    engine = create_engine(
        url,
        echo=settings.db_echo,
        pool_pre_ping=settings.db_pool_pre_ping,
        future=True,
        connect_args=connect_args,
    )
    return engine


engine = _create_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
