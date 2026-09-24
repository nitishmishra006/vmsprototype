"""Shared test fixtures.

Every test gets its own temporary DATA_DIR and SQLite database so nothing touches
the developer's real ./data directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import config as config_module
from app.db import session as session_module


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> config_module.Settings:
    """Point Settings at a temp data dir + DB and clear the settings cache."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    # Don't let a developer's real backend/.env leak into the test run.
    monkeypatch.setitem(config_module.Settings.model_config, "env_file", None)
    config_module.get_settings.cache_clear()
    settings = config_module.get_settings()
    yield settings
    config_module.get_settings.cache_clear()


@pytest.fixture
def db(tmp_settings: config_module.Settings) -> Iterator[Session]:
    session_module.init_engine(tmp_settings.DATABASE_URL)
    session_module.create_all()
    session = session_module.get_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fast_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the slow/environment-dependent probes with deterministic fakes.

    Network (Ollama) and hardware (webcam) probes are never exercised for real in
    the fast suite; the real probes run on the laptop via the acceptance checks.
    """
    from app.services import setup_service

    monkeypatch.setattr(
        setup_service,
        "probe_ollama",
        lambda url, model, timeout=1.5: setup_service.ProbeResult(
            False, "stubbed: not reachable", f"ollama pull {model}"
        ),
    )
    monkeypatch.setattr(
        setup_service,
        "probe_webcam",
        lambda index, timeout_s=3.0: setup_service.ProbeResult(
            True, f"stubbed: index {index} readable at 640x480"
        ),
    )
    monkeypatch.setattr(
        setup_service,
        "probe_hf_model",
        lambda repo_id: setup_service.ProbeResult(
            False, f"stubbed: {repo_id} not cached", f"huggingface-cli download {repo_id}"
        ),
    )
    monkeypatch.setattr(
        setup_service,
        "probe_detector_weights",
        lambda model: setup_service.ProbeResult(True, f"stubbed: {model} found"),
    )


@pytest.fixture
def client(tmp_settings: config_module.Settings, fast_probes: None) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
