"""ModelRegistry: the single place models are created (CLAUDE.md hard rule #2).

Responsibilities:
- register(name, factory): declare how a model is built (lazy).
- get(name): load-once, cached. Records load time, device, model_id, model_version.
- unload(name): free a model (and torch cache / gc if available).
- idle-unload background task using MODEL_IDLE_UNLOAD_SECONDS.
- LOW_MEMORY_MODE mutual-exclusion groups: at most one member of a group resident.
- status(): for /api/health.

No model is ever loaded inside a per-frame function; callers go through get().
"""

from __future__ import annotations

import gc
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelEntry:
    name: str
    factory: Callable[[], Any]
    device: str
    group: str | None = None  # mutual-exclusion group for LOW_MEMORY_MODE
    instance: Any = None
    model_id: str | None = None
    model_version: str | None = None
    load_time_s: float | None = None
    loaded_at: float | None = None
    last_used: float | None = None
    load_error: str | None = None

    @property
    def loaded(self) -> bool:
        return self.instance is not None

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "loaded": self.loaded,
            "device": self.device,
            "group": self.group,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "load_time_s": self.load_time_s,
            "loaded_at": self.loaded_at,
            "last_used": self.last_used,
            "load_error": self.load_error,
        }


class ModelRegistry:
    def __init__(
        self,
        *,
        device: str = "cpu",
        idle_unload_seconds: int = 120,
        low_memory_mode: bool = True,
    ) -> None:
        self._entries: dict[str, ModelEntry] = {}
        self._lock = threading.RLock()
        self.device = device
        self.idle_unload_seconds = idle_unload_seconds
        self.low_memory_mode = low_memory_mode
        self._stop = threading.Event()
        self._reaper: threading.Thread | None = None

    # ---- registration ----------------------------------------------------
    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        *,
        group: str | None = None,
        device: str | None = None,
    ) -> None:
        with self._lock:
            if name in self._entries:
                raise ValueError(f"model {name!r} already registered")
            self._entries[name] = ModelEntry(
                name=name, factory=factory, device=device or self.device, group=group
            )

    def is_registered(self, name: str) -> bool:
        return name in self._entries

    # ---- load / unload ---------------------------------------------------
    def get(self, name: str) -> Any:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                raise KeyError(f"model {name!r} is not registered")
            if entry.loaded:
                entry.last_used = time.time()
                return entry.instance

            # LOW_MEMORY_MODE: unload other resident members of the same group.
            if self.low_memory_mode and entry.group:
                for other in self._entries.values():
                    if other.name != name and other.group == entry.group and other.loaded:
                        logger.info(
                            "low-memory-mode: unloading %s to make room for %s",
                            other.name,
                            name,
                        )
                        self._unload_locked(other)

            start = time.perf_counter()
            try:
                obj = entry.factory()
            except Exception as exc:
                entry.load_error = str(exc)
                logger.exception("model load failed: %s", name)
                raise
            entry.instance = obj
            entry.load_error = None
            entry.load_time_s = time.perf_counter() - start
            entry.loaded_at = time.time()
            entry.last_used = entry.loaded_at
            entry.model_id = getattr(obj, "model_id", None) or name
            entry.model_version = getattr(obj, "model_version", None)
            logger.info(
                "model loaded: %s in %.2fs",
                name,
                entry.load_time_s,
                extra={
                    "model_id": entry.model_id,
                    "model_version": entry.model_version,
                    "device": entry.device,
                },
            )
            return obj

    def unload(self, name: str) -> None:
        with self._lock:
            entry = self._entries.get(name)
            if entry is not None and entry.loaded:
                self._unload_locked(entry)

    def _unload_locked(self, entry: ModelEntry) -> None:
        instance = entry.instance
        entry.instance = None
        entry.loaded_at = None
        # Give the provider a chance to release resources.
        close = getattr(instance, "close", None) or getattr(instance, "unload", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover - defensive
                logger.exception("error closing model %s", entry.name)
        del instance
        gc.collect()
        try:  # free torch CUDA cache if torch is present
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - torch not installed / no cuda
            pass
        logger.info("model unloaded: %s", entry.name)

    # ---- idle reaper -----------------------------------------------------
    def start_idle_reaper(self, poll_seconds: float = 5.0) -> None:
        if self._reaper is not None:
            return
        self._stop.clear()
        self._reaper = threading.Thread(
            target=self._reap_loop, args=(poll_seconds,), name="model-idle-reaper", daemon=True
        )
        self._reaper.start()

    def stop_idle_reaper(self) -> None:
        self._stop.set()
        if self._reaper is not None:
            self._reaper.join(timeout=2.0)
            self._reaper = None

    def _reap_loop(self, poll_seconds: float) -> None:
        while not self._stop.wait(poll_seconds):
            self.reap_idle()

    def reap_idle(self, now: float | None = None) -> list[str]:
        """Unload models idle longer than idle_unload_seconds. Returns names freed."""
        if self.idle_unload_seconds <= 0:
            return []
        now = now if now is not None else time.time()
        freed: list[str] = []
        with self._lock:
            for entry in self._entries.values():
                if (
                    entry.loaded
                    and entry.last_used is not None
                    and now - entry.last_used >= self.idle_unload_seconds
                ):
                    self._unload_locked(entry)
                    freed.append(entry.name)
        return freed

    # ---- introspection ---------------------------------------------------
    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            return [e.status() for e in self._entries.values()]
