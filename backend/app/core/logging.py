"""Structured JSON logging (one JSON object per line).

The traceability fields from SPEC §22 are accepted as optional ``extra`` keys on
any log record and, when present, promoted to top-level keys in the JSON line.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

# Fields from SPEC §22 that we surface at the top level when supplied via `extra`.
TRACE_FIELDS: tuple[str, ...] = (
    "camera_id",
    "stage",
    "model_id",
    "model_version",
    "device",
    "inference_ms",
    "n_detections",
    "plan_id",
    "event_id",
    "vlm_latency_ms",
    "vlm_answer",
    "quality_components",
    "final_decision",
)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    # uvicorn attaches an ANSI-coloured duplicate of the message; it is noise in JSON.
    "color_message",
}


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Promote known trace fields.
        for field in TRACE_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        # Include any other explicit extras that are JSON-friendly.
        for key, value in record.__dict__.items():
            if key in _RESERVED or key in payload or key in TRACE_FIELDS:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
