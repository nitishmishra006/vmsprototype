"""/api/setup-status and the individual probes (with mocked hardware/network)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services import setup_service


def test_setup_status_endpoint_shape(client: TestClient) -> None:
    body = client.get("/api/setup-status").json()
    assert isinstance(body["ok"], bool)
    keys = {item["key"] for item in body["items"]}
    assert {"database", "storage", "disk_space", "detector_weights", "ollama", "webcam"} <= keys
    for item in body["items"]:
        assert set(item) == {"key", "label", "ok", "detail", "fix_command"}


def test_unmet_items_carry_a_fix_command(client: TestClient) -> None:
    body = client.get("/api/setup-status").json()
    unmet = [i for i in body["items"] if not i["ok"]]
    assert unmet, "stubbed probes should leave at least Ollama + HF models unmet"
    for item in unmet:
        assert item["fix_command"], f"{item['key']} is unmet but offers no fix command"


def test_overall_ok_is_false_when_any_item_fails(client: TestClient) -> None:
    assert client.get("/api/setup-status").json()["ok"] is False


# --- individual probes ----------------------------------------------------
def test_probe_storage_ok(tmp_path: Path) -> None:
    result = setup_service.probe_storage(str(tmp_path / "data"))
    assert result.ok
    assert (tmp_path / "data").is_dir()


def test_probe_disk_space_flags_low_space(tmp_path: Path) -> None:
    generous = setup_service.probe_disk_space(str(tmp_path), min_free_gb=0.0)
    assert generous.ok
    impossible = setup_service.probe_disk_space(str(tmp_path), min_free_gb=10**9)
    assert not impossible.ok
    assert impossible.fix_command


def test_probe_detector_weights_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"fake-weights")
    monkeypatch.chdir(tmp_path)
    assert setup_service.probe_detector_weights("yolo11n.pt").ok


def test_probe_detector_weights_missing_gives_download_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    result = setup_service.probe_detector_weights("yolo11n.pt")
    assert not result.ok
    assert "yolo predict" in result.fix_command


def test_probe_hf_model_detects_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    cached = tmp_path / "models--facebook--dinov2-small" / "snapshots" / "abc"
    cached.mkdir(parents=True)
    (cached / "config.json").write_text("{}", encoding="utf-8")
    assert setup_service.probe_hf_model("facebook/dinov2-small").ok

    missing = setup_service.probe_hf_model("HuggingFaceTB/SmolVLM-500M-Instruct")
    assert not missing.ok
    assert "huggingface-cli download" in missing.fix_command


def test_probe_ollama_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def boom(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", boom)
    result = setup_service.probe_ollama("http://localhost:11434", "qwen2.5:1.5b")
    assert not result.ok
    assert "ollama" in result.fix_command.lower()


def test_probe_ollama_reachable_but_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "llama3:8b"}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    result = setup_service.probe_ollama("http://localhost:11434", "qwen2.5:1.5b")
    assert not result.ok
    assert result.fix_command == "ollama pull qwen2.5:1.5b"


def test_probe_ollama_model_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "qwen2.5:1.5b"}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    assert setup_service.probe_ollama("http://localhost:11434", "qwen2.5:1.5b").ok


def test_probe_webcam_missing_opencv_is_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "cv2":
            raise ImportError("no cv2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = setup_service.probe_webcam(0)
    assert not result.ok
    assert "opencv" in result.fix_command


def test_build_setup_status_uses_effective_settings(
    tmp_settings: Settings, fast_probes: None
) -> None:
    from app.db.session import create_all, init_engine

    init_engine(tmp_settings.DATABASE_URL)
    create_all()
    status = setup_service.build_setup_status(tmp_settings)
    assert status["ok"] is False
    webcam = next(i for i in status["items"] if i["key"] == "webcam")
    assert webcam["ok"] is True
