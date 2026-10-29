"""Smoke tests for Alembic migrations.

The SQLite test below runs everywhere. The PostgreSQL test only runs when
``TEST_DATABASE_URL`` points at a live server (GitHub Actions provides one),
because that is the only place the pgvector extension and the HNSW cosine
index from migration ``0003_embeddings`` actually exist.
"""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TABLES = {
    "alembic_version",
    "users",
    "documents",
    "document_chunks",
    "document_pages",
    "conversations",
    "messages",
}


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_and_downgrade_initial_migration(tmp_path: Path) -> None:
    database_path = (tmp_path / "migration-test.db").as_posix()
    database_url = f"sqlite:///{database_path}"
    config = _config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    assert PUBLIC_TABLES <= table_names

    command.downgrade(config, "base")

    remaining_tables = set(inspect(engine).get_table_names())
    assert "users" not in remaining_tables
    assert "documents" not in remaining_tables
    assert "document_pages" not in remaining_tables
    engine.dispose()


def test_postgresql_upgrade_and_downgrade_roundtrip() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; the PostgreSQL migration test is skipped."
        )

    config = _config(database_url)
    engine = create_engine(database_url)

    try:
        # Start from a clean server so a rerun behaves like a fresh one.
        command.downgrade(config, "base")
        command.upgrade(config, "head")

        table_names = set(inspect(engine).get_table_names())
        assert PUBLIC_TABLES <= table_names

        with engine.connect() as connection:
            extension = connection.execute(
                text(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )
            ).scalar()
            assert extension == 1, "the pgvector extension was not enabled"

            index_definition = connection.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname = 'ix_document_chunks_embedding'"
                )
            ).scalar()
            assert index_definition, "the chunk embedding index was not created"
            assert "USING hnsw" in index_definition
            assert "vector_cosine_ops" in index_definition

        command.downgrade(config, "base")

        remaining_tables = set(inspect(engine).get_table_names())
        assert "users" not in remaining_tables
        assert "documents" not in remaining_tables
        assert "document_chunks" not in remaining_tables
    finally:
        engine.dispose()
