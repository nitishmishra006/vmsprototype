"""SQLAlchemy 2.0 ORM models for every table in SPEC §18.

JSON columns use the portable ``JSON`` type (no SQLite-only features) so a
Postgres migration is just an Alembic run. Events carry ``plan_version_id`` and
``concept_version_id`` for full traceability (CLAUDE.md hard rule #9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # webcam|file|rtsp
    source: Mapped[str] = mapped_column(String(1024), nullable=False)  # index|path|url
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    calibration: Mapped[Calibration | None] = relationship(back_populates="camera", uselist=False)
    zones: Mapped[list[Zone]] = relationship(back_populates="camera")


class Calibration(Base, TimestampMixin):
    __tablename__ = "calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), nullable=False, unique=True)
    image_points: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    world_points: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    homography: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    reprojection_error: Mapped[float | None] = mapped_column(Float)

    camera: Mapped[Camera] = relationship(back_populates="calibration")


class Zone(Base, TimestampMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # exclusion | work_area | path | generic
    zone_type: Mapped[str] = mapped_column(String(32), default="generic")
    polygon: Mapped[list[Any]] = mapped_column(JSON, nullable=False)  # normalised coords
    implicit: Mapped[bool] = mapped_column(Boolean, default=False)  # whole_frame

    camera: Mapped[Camera] = relationship(back_populates="zones")


class Anchor(Base, TimestampMixin):
    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(String(512), nullable=False)
    bbox: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    polygon: Mapped[list[Any] | None] = mapped_column(JSON)
    buffer_m: Mapped[float | None] = mapped_column(Float)
    buffer_px: Mapped[float | None] = mapped_column(Float)


class MonitoringPlan(Base, TimestampMixin):
    __tablename__ = "monitoring_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)
    camera_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(32), default="DETERMINISTIC")
    dsl: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)  # full compiled DSL
    event_type: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version_id: Mapped[int | None] = mapped_column(Integer)


class PlanVersion(Base, TimestampMixin):
    __tablename__ = "plan_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("monitoring_plans.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dsl: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    suggestion_id: Mapped[int | None] = mapped_column(Integer)


class TrackedObjectSnapshot(Base):
    __tablename__ = "tracked_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    track_id: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="detector")
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ts: Mapped[float] = mapped_column(Float, nullable=False)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_version_id: Mapped[int | None] = mapped_column(Integer)
    concept_version_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # ALERT|REVIEW|SUPPRESS
    final_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    bindings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_missed_event: Mapped[bool] = mapped_column(Boolean, default=False)
    experimental: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[float] = mapped_column(Float, nullable=False)


class EventEvidence(Base):
    __tablename__ = "event_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    package_key: Mapped[str] = mapped_column(String(512), nullable=False)
    keyframe_keys: Mapped[list[Any]] = mapped_column(JSON, default=list)
    grid_key: Mapped[str | None] = mapped_column(String(512))
    clip_key: Mapped[str | None] = mapped_column(String(512))
    frames_meta: Mapped[list[Any]] = mapped_column(JSON, default=list)


class QualityScore(Base):
    __tablename__ = "quality_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    base_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text)


class VLMResult(Base):
    __tablename__ = "vlm_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    answer: Mapped[str] = mapped_column(String(16))  # yes|no|unclear
    reason: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(128))
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    camera_id: Mapped[str | None] = mapped_column(String(64))
    plan_id: Mapped[str | None] = mapped_column(String(64))
    predicted_event: Mapped[str | None] = mapped_column(String(64))
    final_confidence: Mapped[float | None] = mapped_column(Float)
    components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(16), nullable=False)  # correct|wrong|not_sure
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_keys: Mapped[list[Any]] = mapped_column(JSON, default=list)
    bindings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    user: Mapped[str | None] = mapped_column(String(128))


class VisualConcept(Base, TimestampMixin):
    __tablename__ = "visual_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    prototype: Mapped[list[Any] | None] = mapped_column(JSON)  # L2-normalised mean
    current_version_id: Mapped[int | None] = mapped_column(Integer)


class VisualConceptImage(Base):
    __tablename__ = "visual_concept_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("visual_concepts.id"), nullable=False)
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    embedding: Mapped[list[Any] | None] = mapped_column(JSON)


class ConceptVersion(Base, TimestampMixin):
    __tablename__ = "concept_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("visual_concepts.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prototype: Mapped[list[Any] | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)


class ConceptNegative(Base):
    __tablename__ = "concept_negatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("visual_concepts.id"), nullable=False)
    embedding: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    source_event_id: Mapped[int | None] = mapped_column(Integer)


class UnknownCandidate(Base, TimestampMixin):
    __tablename__ = "unknown_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    crop_key: Mapped[str | None] = mapped_column(String(512))
    embedding: Mapped[list[Any] | None] = mapped_column(JSON)
    ts: Mapped[float] = mapped_column(Float, nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)


class LearningQueueItem(Base, TimestampMixin):
    __tablename__ = "learning_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(64))
    camera_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelVersionRow(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)  # detector|vlm|...
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128))
    device: Mapped[str | None] = mapped_column(String(16))


class SettingsOverride(Base, TimestampMixin):
    __tablename__ = "settings_overrides"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # stored as string, cast on read
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ImprovementSuggestion(Base, TimestampMixin):
    __tablename__ = "improvement_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str | None] = mapped_column(String(64))
    concept_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    replay_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    feedback_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|applied|dismissed


class AppliedImprovement(Base, TimestampMixin):
    __tablename__ = "applied_improvements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int | None] = mapped_column(Integer)
    plan_id: Mapped[str | None] = mapped_column(String(64))
    concept_id: Mapped[int | None] = mapped_column(Integer)
    before_version_id: Mapped[int | None] = mapped_column(Integer)
    after_version_id: Mapped[int | None] = mapped_column(Integer)
    replay_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    user: Mapped[str | None] = mapped_column(String(128))
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)


class ParserExample(Base, TimestampMixin):
    __tablename__ = "parser_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
