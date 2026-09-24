"""Provider interfaces and shared data classes (SPEC §5).

Application code depends on these ABCs, never on a concrete model library
(CLAUDE.md hard rule #3). Concrete providers live in the sibling packages
(detector/, tracker/, grounding/, embedding/, vlm/, parser/, storage/, video/)
and are created only through ``ModelRegistry`` (hard rule #2).

Numpy is imported lazily-friendly: it is a light dependency and is only used for
type hints here, so importing this module does not pull any model library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # keep numpy out of the hard import path for pure-schema use
    import numpy as np

    NDArray = np.ndarray
else:  # pragma: no cover - runtime alias
    NDArray = Any


class ModelUnavailableError(RuntimeError):
    """Raised when a model cannot be loaded/used.

    Carries install instructions so ``/api/health`` and the UI can show the
    feature as unavailable instead of returning fake results (CLAUDE.md rule #1).
    """

    def __init__(self, model: str, reason: str, install_hint: str | None = None) -> None:
        self.model = model
        self.reason = reason
        self.install_hint = install_hint
        msg = f"model {model!r} unavailable: {reason}"
        if install_hint:
            msg += f" | fix: {install_hint}"
        super().__init__(msg)


DetectionSource = Literal["detector", "open_vocab", "concept", "anchor"]


@dataclass
class Detection:
    bbox_xyxy: tuple[float, float, float, float]
    label: str
    confidence: float
    source: DetectionSource = "detector"
    embedding: NDArray | None = None

    @property
    def ground_point_px(self) -> tuple[float, float]:
        """Bottom-centre of the box (SPEC §6)."""
        x1, _y1, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) / 2.0, y2)


@dataclass
class TrackedObject:
    id: str
    type: str
    source: DetectionSource
    bbox: tuple[float, float, float, float]
    confidence: float
    ground_point_px: tuple[float, float]
    first_seen: float
    last_seen: float
    age_frames: int
    speed: float = 0.0
    speed_units: str = "px/s"
    ground_point_m: tuple[float, float] | None = None
    trajectory: list[tuple[float, float, float]] = field(default_factory=list)  # (ts, x, y)
    attributes: dict[str, Any] = field(default_factory=dict)
    static: bool = False


@dataclass
class EventPackage:
    """Everything the VLM / quality engine needs about a candidate event."""

    plan_id: str
    camera_id: str
    event_type: str
    vlm_question: str
    grid_image_jpeg: bytes | None = None
    keyframes: list[bytes] = field(default_factory=list)
    bindings: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)
    frames_meta: list[dict[str, Any]] = field(default_factory=list)
    model_versions: dict[str, str] = field(default_factory=dict)
    timestamps: dict[str, float] = field(default_factory=dict)


@dataclass
class VLMVerdict:
    answer: Literal["yes", "no", "unclear"]
    reason: str
    raw_text: str = ""
    latency_ms: float | None = None
    model_version: str | None = None


@dataclass
class Blocker:
    """A reason a plan cannot start (SPEC §9)."""

    type: str  # camera_missing | zone_missing | calibration_required | ...
    message: str
    fix: dict[str, Any] = field(default_factory=dict)  # {settings_section, prefill}


@dataclass
class Warning_:
    """A non-blocking caveat (SPEC §9). Named with trailing underscore to avoid
    shadowing the builtin ``Warning``."""

    type: str  # parser_fallback_used | approximated_phrase | ...
    message: str
    fix: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    plan: dict[str, Any] | None
    plain_text: str
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)
    unsupported_phrases: list[str] = field(default_factory=list)
    parser_used: str = "unknown"


@dataclass
class ParserContext:
    """Context handed to the parser (SPEC §9)."""

    camera_id: str | None = None
    detector_classes: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    calibrated: bool = False


# --------------------------------------------------------------------------
# Provider ABCs
# --------------------------------------------------------------------------
class DetectorProvider(ABC):
    @abstractmethod
    def detect(self, frame: NDArray) -> list[Detection]: ...

    @property
    @abstractmethod
    def class_names(self) -> list[str]: ...


class OpenVocabularyProvider(ABC):
    @abstractmethod
    def detect(
        self,
        frame: NDArray,
        prompts: list[str],
        box_threshold: float,
        text_threshold: float,
    ) -> list[Detection]: ...


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, image: NDArray) -> NDArray: ...  # L2-normalised

    @abstractmethod
    def embed_batch(self, images: list[NDArray]) -> NDArray: ...

    @staticmethod
    @abstractmethod
    def similarity(a: NDArray, b: NDArray) -> float: ...  # cosine


class TrackerProvider(ABC):
    @abstractmethod
    def update(self, detections: list[Detection], frame_ts: float) -> list[TrackedObject]: ...

    @abstractmethod
    def reset(self) -> None: ...


class VLMProvider(ABC):
    @abstractmethod
    def verify_event(self, pkg: EventPackage) -> VLMVerdict: ...

    @abstractmethod
    def explain_event(self, pkg: EventPackage) -> str: ...


class PlanParserProvider(ABC):
    @abstractmethod
    def parse(self, text: str, context: ParserContext) -> ParseResult: ...


class StorageProvider(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def url(self, key: str) -> str: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class VideoSource(ABC):
    """Laptop webcam, MP4 file, RTSP; WebRTC later."""

    @abstractmethod
    def read_latest(self) -> tuple[NDArray, float] | None: ...
