"""Application settings.

Every key from SPEC §21 lives here, typed, with defaults. Runtime overrides are
merged on top of the .env values by ``app.services.settings_service`` using the
``settings_overrides`` table. No service should hard-code a tunable value; read it
from ``Settings`` instead (CLAUDE.md hard rule #7).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Effective configuration, loaded from environment / .env with defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- runtime / device ------------------------------------------------
    DEVICE: Literal["auto", "cpu", "cuda"] = "auto"
    LOW_MEMORY_MODE: bool = True
    MODEL_IDLE_UNLOAD_SECONDS: int = 120
    DATA_DIR: str = "./data"
    DATABASE_URL: str = "sqlite:///./data/vms.db"

    # ---- webcam ----------------------------------------------------------
    WEBCAM_INDEX: int = 0
    WEBCAM_WIDTH: int = 640
    WEBCAM_HEIGHT: int = 480
    WEBCAM_MAX_PROBE: int = 4

    # ---- camera / detection ---------------------------------------------
    CAMERA_FPS: int = 10
    DETECTION_FPS: int = 4
    DETECT_IMGSZ: int = 416
    DETECTOR_MODEL: str = "yolo11n.pt"
    DETECTOR_CONF: float = 0.35
    DETECTOR_CLASSES: str = "all"  # "all" | comma list e.g. person,car,truck
    TRACK_BUFFER_FRAMES: int = 30
    TRAJECTORY_MAX_POINTS: int = 200
    SPEED_WINDOW_SECONDS: float = 1.0
    CONDITION_GRACE_SECONDS: float = 0.5

    # ---- grounding dino --------------------------------------------------
    GROUNDING_MODEL: str = "IDEA-Research/grounding-dino-tiny"
    GROUNDING_INTERVAL_SECONDS: int = 5
    GROUNDING_BOX_THRESHOLD: float = 0.30
    GROUNDING_TEXT_THRESHOLD: float = 0.25

    # ---- embedding -------------------------------------------------------
    EMBEDDING_MODEL: str = "facebook/dinov2-small"
    EMBEDDING_THRESHOLD: float = 0.70

    # ---- parser ----------------------------------------------------------
    PARSER_BACKEND: Literal["ollama", "regex"] = "ollama"
    OLLAMA_URL: str = "http://localhost:11434"
    PARSER_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_KEEP_ALIVE: str = "60s"

    # ---- vlm -------------------------------------------------------------
    VLM_MODE: Literal["off", "verify", "verify_and_explain"] = "verify"
    VLM_BACKEND: Literal["smolvlm", "ollama"] = "smolvlm"
    VLM_MODEL: str = "HuggingFaceTB/SmolVLM-500M-Instruct"
    MAX_VLM_CONCURRENT_REQUESTS: int = 1
    VLM_TIMEOUT_SECONDS: int = 120

    # ---- evidence --------------------------------------------------------
    EVIDENCE_FPS: int = 2
    EVIDENCE_WIDTH: int = 640
    EVIDENCE_PRE_SECONDS: int = 10
    EVIDENCE_POST_SECONDS: int = 5
    EVIDENCE_RETENTION_DAYS: int = 7
    EVENT_COOLDOWN_SECONDS: int = 30
    MAX_EVENTS_PER_PLAN_PER_MINUTE: int = 4

    # ---- quality engine --------------------------------------------------
    MIN_TRACK_AGE_FRAMES: int = 3
    MIN_DET_CONF: float = 0.35
    QUALITY_WEIGHTS: str = "perception:0.4,tracking:0.3,temporal:0.3,concept:0.3"
    VLM_BOOST: float = 0.5
    VLM_PENALTY: float = 0.5
    ALERT_THRESHOLD: float = 0.70
    REVIEW_THRESHOLD: float = 0.45

    # ---- discovery / improvement ----------------------------------------
    UNKNOWN_DISCOVERY_ENABLED: bool = False
    IMPROVE_MIN_FEEDBACK: int = 3
    IMPROVE_SCAN_INTERVAL_SECONDS: int = 300
    CONCEPT_NEGATIVE_MARGIN: float = 0.05
    RETRAIN_MIN_LABELS: int = 200
    UNKNOWN_SCAN_INTERVAL_SECONDS: int = 30
    SCENE_CHANGE_THRESHOLD: float = 0.25

    # ---- non-.env app knobs ---------------------------------------------
    CORS_ORIGINS: str = "http://localhost:3000"

    @field_validator("QUALITY_WEIGHTS")
    @classmethod
    def _check_quality_weights(cls, v: str) -> str:
        parse_quality_weights(v)  # raises on malformed input
        return v

    @field_validator("DETECTOR_CLASSES")
    @classmethod
    def _check_detector_classes(cls, v: str) -> str:
        if v.strip().lower() != "all" and not v.strip():
            raise ValueError("DETECTOR_CLASSES must be 'all' or a non-empty comma list")
        return v

    # ---- derived helpers -------------------------------------------------
    def quality_weights(self) -> dict[str, float]:
        return parse_quality_weights(self.QUALITY_WEIGHTS)

    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def detector_classes(self) -> str | list[str]:
        raw = self.DETECTOR_CLASSES.strip()
        if raw.lower() == "all":
            return "all"
        return [c.strip() for c in raw.split(",") if c.strip()]


def parse_quality_weights(raw: str) -> dict[str, float]:
    """Parse ``perception:0.4,tracking:0.3,...`` into a dict of floats."""
    weights: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"malformed QUALITY_WEIGHTS entry: {part!r}")
        name, _, value = part.partition(":")
        name = name.strip()
        if not name:
            raise ValueError(f"empty weight name in {part!r}")
        try:
            weights[name] = float(value)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError(f"non-numeric weight in {part!r}") from exc
    if not weights:
        raise ValueError("QUALITY_WEIGHTS produced no entries")
    return weights


# Keys that are genuine runtime-tunable settings (exposed via GET/PATCH /api/settings).
# CORS_ORIGINS is deliberately excluded: changing it needs an app restart.
SETTINGS_KEYS: tuple[str, ...] = tuple(k for k in Settings.model_fields if k != "CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    """Base settings from environment / .env (no DB overrides applied)."""
    return Settings()
