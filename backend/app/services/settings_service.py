"""Effective settings = .env / defaults with the ``settings_overrides`` table on top.

``GET /api/settings`` reports every runtime-tunable key with its value and source
(env|override); ``PATCH /api/settings`` validates against the ``Settings`` types and
rejects unknown keys.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SETTINGS_KEYS, Settings, get_settings
from app.db.models import SettingsOverride

logger = logging.getLogger(__name__)


class UnknownSettingError(KeyError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


class InvalidSettingError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        self.key = key
        self.message = message
        super().__init__(f"{key}: {message}")


def _serialise(value: Any) -> str:
    return json.dumps(value)


def _deserialise(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw  # tolerate hand-edited plain strings


def load_overrides(db: Session) -> dict[str, Any]:
    rows = db.execute(select(SettingsOverride)).scalars().all()
    return {row.key: _deserialise(row.value) for row in rows}


def _validate_single(key: str, value: Any) -> Any:
    """Validate one key against the Settings model and return the coerced value."""
    if key not in SETTINGS_KEYS:
        raise UnknownSettingError(key)
    base = get_settings().model_dump()
    base[key] = value
    try:
        validated = Settings(**base)
    except ValidationError as exc:
        messages = [e.get("msg", "invalid value") for e in exc.errors() if key in e.get("loc", ())]
        raise InvalidSettingError(key, "; ".join(messages) or "invalid value") from exc
    return getattr(validated, key)


def effective_settings(db: Session) -> Settings:
    """Settings with DB overrides applied (invalid rows are ignored and logged)."""
    base = get_settings().model_dump()
    for key, value in load_overrides(db).items():
        if key not in SETTINGS_KEYS:
            logger.warning("ignoring unknown settings override: %s", key)
            continue
        base[key] = value
    try:
        return Settings(**base)
    except ValidationError:
        logger.exception("settings overrides are invalid; falling back to env values")
        return get_settings()


def describe_settings(db: Session) -> list[dict[str, Any]]:
    overrides = load_overrides(db)
    effective = effective_settings(db)
    out: list[dict[str, Any]] = []
    for key in SETTINGS_KEYS:
        value = getattr(effective, key)
        out.append(
            {
                "key": key,
                "value": value.value if hasattr(value, "value") else value,
                "source": "override" if key in overrides else "env",
                "type": type(getattr(get_settings(), key)).__name__,
            }
        )
    return out


def set_overrides(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist overrides. Raises on unknown or invalid keys."""
    coerced: dict[str, Any] = {}
    for key, value in values.items():
        coerced[key] = _validate_single(key, value)

    for key, value in coerced.items():
        stored = value.value if hasattr(value, "value") else value
        row = db.get(SettingsOverride, key)
        if row is None:
            db.add(SettingsOverride(key=key, value=_serialise(stored)))
        else:
            row.value = _serialise(stored)
        logger.info("settings override set", extra={"stage": "settings", "setting_key": key})
    db.flush()
    return coerced


def reset_overrides(db: Session, keys: list[str]) -> list[str]:
    """Drop overrides so the .env / default value applies again."""
    removed: list[str] = []
    for key in keys:
        if key not in SETTINGS_KEYS:
            raise UnknownSettingError(key)
        row = db.get(SettingsOverride, key)
        if row is not None:
            db.delete(row)
            removed.append(key)
    db.flush()
    return removed
