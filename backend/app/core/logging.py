"""Structured logging for the API (Phase 5.3).

Two formats share the same records:

- ``plain``  one human-readable line per event, for development consoles;
- ``json``   one JSON object per line, so a log collector can index
             ``event``, ``request_id``, and ``duration_ms`` without
             parsing free text.

Loggers pass extra fields alongside the message; the JSON formatter
serializes them and drops the Python internals that would only add noise.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import Settings

# Attributes the logging module puts on every record itself, so the JSON
# formatter keeps only the fields the caller added on top.
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}

# The handler this module owns. Repeated calls update it in place instead
# of stacking duplicate lines on the root logger.
_handler: logging.Handler | None = None


class JsonFormatter(logging.Formatter):
    """Render one record as a JSON object with its structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Install the root handler and level for this process."""

    global _handler

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    if _handler is None or _handler not in root.handlers:
        _handler = logging.StreamHandler(sys.stderr)
        root.addHandler(_handler)
    _handler.setFormatter(formatter)
