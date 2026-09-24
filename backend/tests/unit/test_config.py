"""Settings, quality-weight parsing and runtime overrides."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings, parse_quality_weights
from app.services.settings_service import (
    InvalidSettingError,
    UnknownSettingError,
    describe_settings,
    effective_settings,
    reset_overrides,
    set_overrides,
)


def test_every_spec_key_has_a_default(tmp_settings: Settings) -> None:
    # A representative sample across every SPEC §21 group.
    for key in (
        "DEVICE",
        "LOW_MEMORY_MODE",
        "MODEL_IDLE_UNLOAD_SECONDS",
        "WEBCAM_INDEX",
        "DETECTION_FPS",
        "DETECTOR_MODEL",
        "GROUNDING_MODEL",
        "EMBEDDING_THRESHOLD",
        "PARSER_MODEL",
        "VLM_MODE",
        "EVIDENCE_FPS",
        "ALERT_THRESHOLD",
        "REVIEW_THRESHOLD",
        "UNKNOWN_DISCOVERY_ENABLED",
        "IMPROVE_MIN_FEEDBACK",
        "SCENE_CHANGE_THRESHOLD",
    ):
        assert hasattr(tmp_settings, key), f"missing setting: {key}"


def test_defaults_match_spec(tmp_settings: Settings) -> None:
    assert tmp_settings.DETECT_IMGSZ == 416
    assert tmp_settings.ALERT_THRESHOLD == 0.70
    assert tmp_settings.REVIEW_THRESHOLD == 0.45
    assert tmp_settings.VLM_MODE == "verify"
    assert tmp_settings.LOW_MEMORY_MODE is True


def test_quality_weights_parsing() -> None:
    weights = parse_quality_weights("perception:0.4,tracking:0.3,temporal:0.3,concept:0.3")
    assert weights == {
        "perception": 0.4,
        "tracking": 0.3,
        "temporal": 0.3,
        "concept": 0.3,
    }


@pytest.mark.parametrize("bad", ["", "perception", "perception:abc", "   "])
def test_quality_weights_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_quality_weights(bad)


def test_detector_classes_helper(tmp_settings: Settings) -> None:
    assert tmp_settings.detector_classes() == "all"
    custom = Settings(DETECTOR_CLASSES="person, car , truck")
    assert custom.detector_classes() == ["person", "car", "truck"]


def test_override_changes_effective_value(db: Session) -> None:
    before = effective_settings(db)
    assert before.ALERT_THRESHOLD == 0.70

    set_overrides(db, {"ALERT_THRESHOLD": 0.9})
    db.commit()

    after = effective_settings(db)
    assert after.ALERT_THRESHOLD == 0.9


def test_override_source_is_reported(db: Session) -> None:
    set_overrides(db, {"DETECTION_FPS": 6})
    db.commit()

    described = {row["key"]: row for row in describe_settings(db)}
    assert described["DETECTION_FPS"]["value"] == 6
    assert described["DETECTION_FPS"]["source"] == "override"
    assert described["ALERT_THRESHOLD"]["source"] == "env"


def test_override_persists_across_new_session(db: Session) -> None:
    set_overrides(db, {"EVIDENCE_FPS": 5})
    db.commit()
    db.close()

    from app.db.session import get_session

    fresh = get_session()
    try:
        assert effective_settings(fresh).EVIDENCE_FPS == 5
    finally:
        fresh.close()


def test_reset_restores_env_value(db: Session) -> None:
    set_overrides(db, {"ALERT_THRESHOLD": 0.95})
    db.commit()
    assert effective_settings(db).ALERT_THRESHOLD == 0.95

    reset_overrides(db, ["ALERT_THRESHOLD"])
    db.commit()
    assert effective_settings(db).ALERT_THRESHOLD == get_settings().ALERT_THRESHOLD


def test_unknown_key_rejected(db: Session) -> None:
    with pytest.raises(UnknownSettingError):
        set_overrides(db, {"NOT_A_SETTING": 1})


def test_invalid_value_rejected(db: Session) -> None:
    with pytest.raises(InvalidSettingError):
        set_overrides(db, {"DETECTION_FPS": "not-a-number"})
    with pytest.raises(InvalidSettingError):
        set_overrides(db, {"VLM_MODE": "sometimes"})


def test_cors_origins_not_runtime_tunable(db: Session) -> None:
    # Changing CORS needs a restart, so it must not be exposed as an override.
    with pytest.raises(UnknownSettingError):
        set_overrides(db, {"CORS_ORIGINS": "http://evil.example"})
