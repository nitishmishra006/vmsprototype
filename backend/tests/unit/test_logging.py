"""Structured JSON logging (SPEC §22, CLAUDE.md hard rule #8)."""

from __future__ import annotations

import json
import logging

from app.core.logging import TRACE_FIELDS, JsonFormatter


def _format(record: logging.LogRecord) -> dict[str, object]:
    return json.loads(JsonFormatter().format(record))


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_output_is_one_json_object_per_line() -> None:
    line = JsonFormatter().format(_record())
    assert "\n" not in line
    payload = json.loads(line)
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["ts"].endswith("+00:00")


def test_spec_22_trace_fields_are_promoted() -> None:
    payload = _format(
        _record(
            camera_id="CAM_01",
            stage="inference",
            model_id="yolo11n",
            model_version="8.3.0",
            device="cpu",
            inference_ms=42.5,
            n_detections=3,
            plan_id="plan_1",
            event_id=7,
            vlm_latency_ms=1200.0,
            vlm_answer="yes",
            quality_components={"perception": 0.8},
            final_decision="ALERT",
        )
    )
    for field in TRACE_FIELDS:
        assert field in payload, f"SPEC §22 field missing from log output: {field}"
    assert payload["quality_components"] == {"perception": 0.8}
    assert payload["final_decision"] == "ALERT"


def test_internal_record_attributes_are_not_leaked() -> None:
    payload = _format(_record())
    for noisy in ("args", "msecs", "levelno", "pathname", "color_message"):
        assert noisy not in payload


def test_uvicorn_color_message_is_stripped() -> None:
    payload = _format(_record(color_message="\x1b[36mcoloured\x1b[0m"))
    assert "color_message" not in payload


def test_exception_is_captured() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record()
        record.exc_info = sys.exc_info()
        payload = _format(record)
    assert "boom" in payload["exc"]


def test_non_serialisable_extra_does_not_crash() -> None:
    payload = _format(_record(weird=object()))
    assert "weird" in payload  # rendered via default=str rather than raising
