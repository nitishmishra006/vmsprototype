"""ModelRegistry: lazy load-once, idle unload, LOW_MEMORY_MODE mutual exclusion."""

from __future__ import annotations

import pytest

from app.core.device import resolve_device
from app.core.model_registry import ModelRegistry
from app.providers.base import ModelUnavailableError


class FakeModel:
    def __init__(self, name: str) -> None:
        self.model_id = name
        self.model_version = "1.2.3"
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_factory_not_called_until_get() -> None:
    calls: list[str] = []
    registry = ModelRegistry()
    registry.register("detector", lambda: calls.append("loaded") or FakeModel("detector"))
    assert calls == []
    registry.get("detector")
    assert calls == ["loaded"]


def test_model_loads_once_and_is_cached() -> None:
    calls: list[int] = []

    def factory() -> FakeModel:
        calls.append(1)
        return FakeModel("detector")

    registry = ModelRegistry()
    registry.register("detector", factory)
    first = registry.get("detector")
    second = registry.get("detector")
    assert first is second
    assert len(calls) == 1


def test_status_records_version_and_load_time() -> None:
    registry = ModelRegistry(device="cpu")
    registry.register("vlm", lambda: FakeModel("smolvlm"))
    registry.get("vlm")
    status = next(s for s in registry.status() if s["name"] == "vlm")
    assert status["loaded"] is True
    assert status["model_id"] == "smolvlm"
    assert status["model_version"] == "1.2.3"
    assert status["device"] == "cpu"
    assert status["load_time_s"] is not None


def test_unload_calls_close_and_clears_instance() -> None:
    registry = ModelRegistry()
    model = FakeModel("vlm")
    registry.register("vlm", lambda: model)
    registry.get("vlm")
    registry.unload("vlm")
    assert model.closed is True
    assert next(s for s in registry.status() if s["name"] == "vlm")["loaded"] is False


def test_low_memory_mode_keeps_one_model_per_group() -> None:
    registry = ModelRegistry(low_memory_mode=True)
    registry.register("grounding", lambda: FakeModel("grounding"), group="heavy")
    registry.register("vlm", lambda: FakeModel("vlm"), group="heavy")
    registry.register("embedding", lambda: FakeModel("embedding"))  # no group

    registry.get("grounding")
    registry.get("embedding")
    registry.get("vlm")  # must evict grounding, not embedding

    loaded = {s["name"] for s in registry.status() if s["loaded"]}
    assert loaded == {"vlm", "embedding"}


def test_low_memory_mode_off_keeps_both_resident() -> None:
    registry = ModelRegistry(low_memory_mode=False)
    registry.register("grounding", lambda: FakeModel("grounding"), group="heavy")
    registry.register("vlm", lambda: FakeModel("vlm"), group="heavy")
    registry.get("grounding")
    registry.get("vlm")
    assert {s["name"] for s in registry.status() if s["loaded"]} == {"grounding", "vlm"}


def test_idle_reaper_unloads_stale_models() -> None:
    registry = ModelRegistry(idle_unload_seconds=60)
    registry.register("vlm", lambda: FakeModel("vlm"))
    registry.get("vlm")

    assert registry.reap_idle(now=0) == []  # just used
    freed = registry.reap_idle(now=10**12)  # far in the future
    assert freed == ["vlm"]


def test_idle_unload_disabled_when_zero() -> None:
    registry = ModelRegistry(idle_unload_seconds=0)
    registry.register("vlm", lambda: FakeModel("vlm"))
    registry.get("vlm")
    assert registry.reap_idle(now=10**12) == []


def test_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        ModelRegistry().get("nope")


def test_duplicate_registration_raises() -> None:
    registry = ModelRegistry()
    registry.register("detector", lambda: FakeModel("d"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register("detector", lambda: FakeModel("d"))


def test_load_failure_is_recorded_and_reraised() -> None:
    def boom() -> FakeModel:
        raise ModelUnavailableError("yolo11n.pt", "weights missing", "yolo predict model=...")

    registry = ModelRegistry()
    registry.register("detector", boom)
    with pytest.raises(ModelUnavailableError):
        registry.get("detector")
    status = next(s for s in registry.status() if s["name"] == "detector")
    assert status["loaded"] is False
    assert "weights missing" in status["load_error"]


def test_model_unavailable_error_message_has_fix_hint() -> None:
    err = ModelUnavailableError("smolvlm", "not downloaded", "huggingface-cli download X")
    assert "not downloaded" in str(err)
    assert "huggingface-cli download X" in str(err)


# --- device resolution ----------------------------------------------------
def test_device_cpu_is_explicit() -> None:
    decision = resolve_device("cpu")
    assert decision.device == "cpu"
    assert "explicitly requested" in decision.reason


def test_device_auto_falls_back_to_cpu_without_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.device._cuda_available", lambda: False)
    decision = resolve_device("auto")
    assert decision.device == "cpu"
    assert "no cuda" in decision.reason


def test_device_auto_picks_cuda_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.device._cuda_available", lambda: True)
    assert resolve_device("auto").device == "cuda"


def test_cuda_requested_without_cuda_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.core.device._cuda_available", lambda: False)
    with caplog.at_level("WARNING"):
        decision = resolve_device("cuda")
    assert decision.device == "cpu"
    # No silent fallbacks (CLAUDE.md hard rule #5).
    assert any(r.levelname == "WARNING" for r in caplog.records)
