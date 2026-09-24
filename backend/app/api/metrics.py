"""GET /api/metrics — process RSS, system RAM, CPU, GPU (torch imported lazily)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import MetricsResponse

router = APIRouter()

_MB = 1024 * 1024


def _gpu_metrics() -> dict[str, object] | None:
    """Return GPU memory info if torch+CUDA are present. torch is imported here,
    never at module level (CLAUDE.md hard rule #2)."""
    try:
        import torch
    except Exception:
        return None
    try:
        if not torch.cuda.is_available():
            return None
        index = torch.cuda.current_device()
        free_b, total_b = torch.cuda.mem_get_info(index)
        return {
            "name": torch.cuda.get_device_name(index),
            "allocated_mb": torch.cuda.memory_allocated(index) / _MB,
            "reserved_mb": torch.cuda.memory_reserved(index) / _MB,
            "free_mb": free_b / _MB,
            "total_mb": total_b / _MB,
        }
    except Exception:  # pragma: no cover - driver-specific
        return None


@router.get("/metrics", response_model=MetricsResponse, tags=["system"])
def metrics() -> MetricsResponse:
    import psutil

    process = psutil.Process()
    virtual = psutil.virtual_memory()
    return MetricsResponse(
        process_rss_mb=process.memory_info().rss / _MB,
        # interval=None returns the value since the previous call (non-blocking).
        process_cpu_percent=process.cpu_percent(interval=None),
        system_ram_total_mb=virtual.total / _MB,
        system_ram_available_mb=virtual.available / _MB,
        system_ram_percent=virtual.percent,
        gpu=_gpu_metrics(),
    )
