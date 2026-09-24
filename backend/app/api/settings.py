"""GET/PATCH /api/settings — effective values and runtime overrides."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import db_dependency
from app.schemas.api import SettingsPatchRequest, SettingsResponse, SettingValue
from app.services.settings_service import (
    InvalidSettingError,
    UnknownSettingError,
    describe_settings,
    reset_overrides,
    set_overrides,
)

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse, tags=["system"])
def get_settings_endpoint(db: Session = Depends(db_dependency)) -> SettingsResponse:
    return SettingsResponse(settings=[SettingValue(**s) for s in describe_settings(db)])


@router.patch("/settings", response_model=SettingsResponse, tags=["system"])
def patch_settings_endpoint(
    payload: SettingsPatchRequest, db: Session = Depends(db_dependency)
) -> SettingsResponse:
    try:
        if payload.reset:
            reset_overrides(db, payload.reset)
        if payload.values:
            set_overrides(db, payload.values)
    except UnknownSettingError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown setting: {exc.key}",
        ) from exc
    except InvalidSettingError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    db.commit()
    return SettingsResponse(settings=[SettingValue(**s) for s in describe_settings(db)])
