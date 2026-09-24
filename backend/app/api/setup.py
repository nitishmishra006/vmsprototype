"""GET /api/setup-status — the Settings page checklist."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import db_dependency
from app.schemas.api import SetupStatusResponse
from app.services.settings_service import effective_settings
from app.services.setup_service import build_setup_status

router = APIRouter()


@router.get("/setup-status", response_model=SetupStatusResponse, tags=["system"])
def setup_status(db: Session = Depends(db_dependency)) -> SetupStatusResponse:
    settings = effective_settings(db)
    return SetupStatusResponse(**build_setup_status(settings))
