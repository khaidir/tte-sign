"""JSON logging with contextvars for request_id."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        ts = (
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{datetime.now(UTC).microsecond:06d}Z"
        )  # noqa: E501
        obj: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Add extra fields
        for key, value in getattr(record, "extra", {}).items():
            obj[key] = value
        # Include request_id from context if not already in extra
        if "request_id" not in obj:
            rid = get_request_id()
            if rid:
                obj["request_id"] = rid
        # Include exception info
        if record.exc_info and record.exc_info[0]:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatting to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
