"""Setup checklist behind ``GET /api/setup-status`` (SPEC §17, Prompt 0).

Each item reports ``ok``, a human ``detail`` and the exact ``fix_command`` to run.
Every probe is a small, individually-mockable function and every probe is defensive:
a probe that cannot run reports ``ok=False`` with the reason, never an exception and
never a fake success (CLAUDE.md hard rule #1).
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)

#: Free disk below this is flagged.
MIN_FREE_DISK_GB = 5.0

#: HF repos the prototype needs, with the phase that first uses each.
HF_MODELS: tuple[tuple[str, str], ...] = (
    ("GROUNDING_MODEL", "Grounding DINO (Phase 5)"),
    ("EMBEDDING_MODEL", "DINOv2 embeddings (Phase 6)"),
    ("VLM_MODEL", "VLM verification (Phase 7)"),
)


@dataclass
class ProbeResult:
    ok: bool
    detail: str = ""
    fix_command: str | None = None


# --------------------------------------------------------------------------
# individual probes
# --------------------------------------------------------------------------
def probe_database(database_url: str) -> ProbeResult:
    try:
        from sqlalchemy import text

        from app.db.session import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return ProbeResult(True, f"connected ({database_url})")
    except Exception as exc:
        return ProbeResult(
            False,
            f"cannot reach database: {exc}",
            "check DATABASE_URL in backend/.env, then: alembic upgrade head",
        )


def probe_storage(data_dir: str) -> ProbeResult:
    path = Path(data_dir).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / ".write-probe"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        return ProbeResult(True, f"writable ({path.resolve()})")
    except Exception as exc:
        return ProbeResult(False, f"not writable: {exc}", f"mkdir -p {path} && chmod u+w {path}")


def probe_disk_space(data_dir: str, min_free_gb: float = MIN_FREE_DISK_GB) -> ProbeResult:
    try:
        target = Path(data_dir).expanduser()
        probe_path = target if target.exists() else Path.cwd()
        usage = shutil.disk_usage(probe_path)
        free_gb = usage.free / (1024**3)
        if free_gb < min_free_gb:
            return ProbeResult(
                False,
                f"{free_gb:.1f} GB free (want >= {min_free_gb:.0f} GB for models + evidence)",
                "free up disk space, or lower EVIDENCE_RETENTION_DAYS",
            )
        return ProbeResult(True, f"{free_gb:.1f} GB free")
    except Exception as exc:
        return ProbeResult(False, f"cannot determine free space: {exc}")


def _detector_weight_candidates(detector_model: str) -> list[Path]:
    name = Path(detector_model)
    candidates = [name, Path.cwd() / name, Path.cwd().parent / name]
    # Ultralytics also keeps weights in its settings dir.
    home = Path.home()
    candidates += [
        home / ".config" / "Ultralytics" / name.name,
        home / "Library" / "Application Support" / "Ultralytics" / name.name,
    ]
    return candidates


def probe_detector_weights(detector_model: str) -> ProbeResult:
    for candidate in _detector_weight_candidates(detector_model):
        try:
            if candidate.exists():  # .pt file or exported OpenVINO folder
                return ProbeResult(True, f"found at {candidate}")
        except OSError:  # pragma: no cover - unreadable path
            continue
    return ProbeResult(
        False,
        f"{detector_model} not found",
        f"yolo predict model={detector_model} source=https://ultralytics.com/images/bus.jpg",
    )


def _hf_cache_root() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def probe_hf_model(repo_id: str) -> ProbeResult:
    folder = "models--" + repo_id.replace("/", "--")
    path = _hf_cache_root() / folder
    try:
        if path.is_dir() and any(path.rglob("*")):
            return ProbeResult(True, f"present in HF cache ({path})")
    except OSError as exc:  # pragma: no cover - unreadable cache
        return ProbeResult(False, f"cannot read HF cache: {exc}")
    return ProbeResult(
        False,
        f"{repo_id} not in local HF cache",
        f"huggingface-cli download {repo_id}",
    )


def probe_ollama(ollama_url: str, parser_model: str, timeout: float = 1.5) -> ProbeResult:
    try:
        import httpx

        response = httpx.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return ProbeResult(
            False,
            f"Ollama not reachable at {ollama_url}: {exc}",
            "install from https://ollama.com, then: ollama serve",
        )
    names = [m.get("name", "") for m in payload.get("models", [])]
    base_names = {n.split(":")[0] for n in names}
    if parser_model in names or parser_model.split(":")[0] in base_names:
        return ProbeResult(True, f"reachable; {parser_model} pulled")
    return ProbeResult(
        False,
        f"reachable, but {parser_model} is not pulled (have: {', '.join(names) or 'none'})",
        f"ollama pull {parser_model}",
    )


def probe_webcam(index: int, timeout_s: float = 3.0) -> ProbeResult:
    """Open the webcam briefly and release it immediately.

    Never leaves the device held: the capture is released in a finally block.
    """
    try:
        import cv2
    except ImportError:
        return ProbeResult(False, "opencv not installed", "pip install opencv-python")

    cap = None
    try:
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            return ProbeResult(
                False,
                f"webcam index {index} could not be opened (in use by another app, "
                "or camera permission not granted)",
                "close Zoom/Teams/Meet; on macOS allow Camera for your terminal in "
                "System Settings > Privacy & Security > Camera",
            )
        ok, frame = cap.read()
        if not ok or frame is None:
            return ProbeResult(
                False,
                f"webcam index {index} opened but returned no frame",
                "close other apps using the camera and retry",
            )
        height, width = frame.shape[:2]
        return ProbeResult(True, f"index {index} readable at {width}x{height}")
    except Exception as exc:  # pragma: no cover - driver-specific failures
        return ProbeResult(False, f"webcam probe failed: {exc}")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:  # pragma: no cover - defensive
                logger.warning("failed to release webcam probe capture")


# --------------------------------------------------------------------------
# checklist assembly
# --------------------------------------------------------------------------
def build_setup_status(settings: Settings) -> dict[str, object]:
    items: list[dict[str, object]] = []

    def add(key: str, label: str, result: ProbeResult) -> None:
        items.append(
            {
                "key": key,
                "label": label,
                "ok": result.ok,
                "detail": result.detail,
                "fix_command": result.fix_command,
            }
        )

    add("database", "Database", probe_database(settings.DATABASE_URL))
    add("storage", "Data directory", probe_storage(settings.DATA_DIR))
    add("disk_space", "Free disk space", probe_disk_space(settings.DATA_DIR))
    add("detector_weights", "Detector weights", probe_detector_weights(settings.DETECTOR_MODEL))
    add(
        "ollama",
        "Ollama + parser model",
        probe_ollama(settings.OLLAMA_URL, settings.PARSER_MODEL),
    )
    for field_name, label in HF_MODELS:
        repo_id = getattr(settings, field_name)
        add(f"hf_{field_name.lower()}", label, probe_hf_model(repo_id))
    add("webcam", "Webcam", probe_webcam(settings.WEBCAM_INDEX))

    return {"ok": all(bool(i["ok"]) for i in items), "items": items}
