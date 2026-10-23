"""Database connectivity checks."""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine

logger = logging.getLogger(__name__)


def check_database(target: Engine | None = None) -> bool:
    """Return True when a simple query succeeds against the database."""

    db_engine = target or engine

    try:
        with db_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Database health check failed: %s", exc)
        return False
