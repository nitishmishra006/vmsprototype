"""Process-wide singletons wired at startup by the FastAPI lifespan.

Keeping them here (rather than importing models directly in routers) is what lets
API modules stay free of torch/transformers imports at module level
(CLAUDE.md hard rule #2).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.device import DeviceDecision
from app.core.model_registry import ModelRegistry
from app.providers.base import StorageProvider

APP_VERSION = "0.1.0"
CURRENT_PHASE = 0


@dataclass
class AppState:
    registry: ModelRegistry | None = None
    storage: StorageProvider | None = None
    device: DeviceDecision | None = None

    def require_registry(self) -> ModelRegistry:
        if self.registry is None:
            raise RuntimeError("model registry not initialised")
        return self.registry

    def require_storage(self) -> StorageProvider:
        if self.storage is None:
            raise RuntimeError("storage provider not initialised")
        return self.storage


state = AppState()
