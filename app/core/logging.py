"""
Structured logging configuration.

We deliberately avoid a heavyweight logging framework. A single JSON-ish
formatter with contextual fields (processing_id, survey_id, stage, etc.)
is enough for a hackathon backend and keeps behaviour easy to reason
about; it can be swapped for structlog later without touching call
sites, since everything logs through the standard `logging` module.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class ContextualJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with any `extra` fields included."""

    RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in self.RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Attach a single JSON stream handler to the root logger."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Avoid duplicate handlers if configure_logging is called more than once
    # (e.g. under the test runner + uvicorn's --reload subprocess).
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ContextualJSONFormatter())
    root.addHandler(handler)

    # Quiet down noisy third-party loggers while keeping our own verbose.
    logging.getLogger("uvicorn.access").setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
