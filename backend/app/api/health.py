"""GET /api/health — is the service up, and which features are actually usable."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.state import APP_VERSION, CURRENT_PHASE, state
from app.db.session import db_dependency
from app.schemas.api import FeatureStatus, HealthModelStatus, HealthResponse
from app.services import setup_service
from app.services.settings_service import effective_settings

router = APIRouter()


def _feature_statuses(settings: Settings) -> list[FeatureStatus]:
    """Report each model-backed feature as available or not.

    A feature whose model is missing is reported unavailable with the fix command;
    it is never silently treated as working (CLAUDE.md hard rule #1).
    """
    detector = setup_service.probe_detector_weights(settings.DETECTOR_MODEL)
    grounding = setup_service.probe_hf_model(settings.GROUNDING_MODEL)
    embedding = setup_service.probe_hf_model(settings.EMBEDDING_MODEL)
    vlm = setup_service.probe_hf_model(settings.VLM_MODEL)
    parser = setup_service.probe_ollama(settings.OLLAMA_URL, settings.PARSER_MODEL)

    return [
        FeatureStatus(
            name="detection",
            available=detector.ok,
            detail=detector.detail,
            fix_command=detector.fix_command,
        ),
        FeatureStatus(
            name="open_vocab",
            available=grounding.ok,
            detail=grounding.detail,
            fix_command=grounding.fix_command,
        ),
        FeatureStatus(
            name="concepts",
            available=embedding.ok,
            detail=embedding.detail,
            fix_command=embedding.fix_command,
        ),
        FeatureStatus(
            name="vlm",
            available=vlm.ok and settings.VLM_MODE != "off",
            detail=vlm.detail if settings.VLM_MODE != "off" else "VLM_MODE=off",
            fix_command=vlm.fix_command,
        ),
        FeatureStatus(
            name="nl_parser",
            available=parser.ok,
            detail=parser.detail,
            fix_command=parser.fix_command,
        ),
    ]


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(db: Session = Depends(db_dependency)) -> HealthResponse:
    settings = effective_settings(db)

    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    storage_ok = state.storage is not None
    device = state.device

    models = [HealthModelStatus(**s) for s in (state.registry.status() if state.registry else [])]
    features = _feature_statuses(settings)

    return HealthResponse(
        status="ok" if database_ok and storage_ok else "degraded",
        version=APP_VERSION,
        phase=CURRENT_PHASE,
        device=device.device if device else "unknown",
        device_reason=device.reason if device else "device not resolved",
        database=database_ok,
        storage=storage_ok,
        models=models,
        features=features,
    )
