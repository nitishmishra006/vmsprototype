"""Device resolution for model loading.

``DEVICE=auto`` picks CUDA when available, otherwise CPU. The decision and its
reason are logged; a WARNING is emitted if CUDA is explicitly requested but not
available (CLAUDE.md hard rule #5: no silent fallbacks).

torch is imported lazily so importing this module never pulls torch into API
modules at import time (CLAUDE.md hard rule #2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceDecision:
    device: str  # "cpu" | "cuda"
    reason: str
    cuda_available: bool


def _cuda_available() -> bool:
    try:
        import torch  # noqa: PLC0415 (lazy import by design)
    except Exception:  # pragma: no cover - torch not installed in Phase 0 tests
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - defensive
        return False


def resolve_device(requested: str) -> DeviceDecision:
    """Resolve ``auto|cpu|cuda`` into a concrete device with a logged reason."""
    requested = (requested or "auto").lower()
    cuda = _cuda_available()

    if requested == "cpu":
        decision = DeviceDecision("cpu", "cpu explicitly requested", cuda)
    elif requested == "cuda":
        if cuda:
            decision = DeviceDecision("cuda", "cuda explicitly requested and available", cuda)
        else:
            decision = DeviceDecision(
                "cpu", "cuda requested but not available; falling back to cpu", cuda
            )
    else:  # auto
        if cuda:
            decision = DeviceDecision("cuda", "auto selected cuda (available)", cuda)
        else:
            decision = DeviceDecision("cpu", "auto selected cpu (no cuda)", cuda)

    if requested == "cuda" and not cuda:
        logger.warning("device fallback: %s", decision.reason, extra={"device": decision.device})
    else:
        logger.info("device resolved: %s", decision.reason, extra={"device": decision.device})
    return decision
