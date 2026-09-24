"""Assembles every router under the /api prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health, metrics, settings, setup, stubs

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(setup.router)
api_router.include_router(settings.router)
# Stubs are included last so a real implementation registered above always wins.
api_router.include_router(stubs.router)
