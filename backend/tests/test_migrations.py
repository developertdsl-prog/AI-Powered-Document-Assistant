"""Smoke tests for Alembic migrations."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
    assert {
        "alembic_version",
        "users",
        "documents",
        "document_chunks",
        "document_pages",
        "conversations",
        "messages",
    } <= table_names

    command.downgrade(config, "base")

    remaining_tables = set(inspect(engine).get_table_names())
    assert "users" not in remaining_tables
    assert "documents" not in remaining_tables
    assert "document_pages" not in remaining_tables
    engine.dispose()
