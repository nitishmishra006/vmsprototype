"""FastAPI application entry point.

Startup order matters: logging → settings → DB engine → storage → device → model
registry (empty in Phase 0; providers register themselves from Phase 1). Nothing
here imports torch or transformers (CLAUDE.md hard rule #2).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.device import resolve_device
from app.core.logging import configure_logging
from app.core.model_registry import ModelRegistry
from app.core.state import APP_VERSION, CURRENT_PHASE, state
from app.db.session import create_all, init_engine, session_scope
from app.providers.storage.local import LocalStorageProvider
from app.services.settings_service import effective_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()

    init_engine(settings.DATABASE_URL)
    # Phase 0 convenience: ensure tables exist even before `alembic upgrade head`.
    create_all()

    # Re-read settings with DB overrides applied.
    with session_scope() as db:
        settings = effective_settings(db)

    state.storage = LocalStorageProvider(settings.DATA_DIR)
    state.device = resolve_device(settings.DEVICE)
    state.registry = ModelRegistry(
        device=state.device.device,
        idle_unload_seconds=settings.MODEL_IDLE_UNLOAD_SECONDS,
        low_memory_mode=settings.LOW_MEMORY_MODE,
    )
    state.registry.start_idle_reaper()

    logger.info(
        "vision-vms backend started",
        extra={"stage": "startup", "device": state.device.device},
    )
    try:
        yield
    finally:
        if state.registry is not None:
            state.registry.stop_idle_reaper()
        logger.info("vision-vms backend stopped", extra={"stage": "shutdown"})


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vision VMS",
        description="Natural-language Vision Management System prototype",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    # CORS is configured from settings at import time; changing it needs a restart.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/", tags=["system"])
    def root() -> dict[str, object]:
        return {
            "name": "Vision VMS",
            "version": APP_VERSION,
            "phase": CURRENT_PHASE,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
