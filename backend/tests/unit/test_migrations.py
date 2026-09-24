"""`alembic upgrade head` must work on a fresh clone.

Regression test for the Phase 0 acceptance failure: Alembic builds its own engine
and so bypassed ``init_engine``'s directory creation, making the documented setup
sequence fail with "unable to open database file" before ``backend/data/`` existed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config
from app.core import config as config_module

BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: Every table SPEC §18 requires.
SPEC_18_TABLES = {
    "cameras",
    "calibrations",
    "zones",
    "anchors",
    "monitoring_plans",
    "tracked_objects",
    "events",
    "event_evidence",
    "quality_scores",
    "vlm_results",
    "feedback",
    "visual_concepts",
    "visual_concept_images",
    "unknown_candidates",
    "learning_queue",
    "model_versions",
    "settings_overrides",
    "plan_versions",
    "concept_versions",
    "concept_negatives",
    "improvement_suggestions",
    "applied_improvements",
    "parser_examples",
}


def _alembic_config() -> Config:
    # Built without alembic.ini so the test does not reconfigure global logging.
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _tables(db_path: Path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in rows}
    finally:
        connection.close()


@pytest.fixture
def fresh_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A DATABASE_URL whose parent directory does not exist yet."""
    db_path = tmp_path / "data" / "vms.db"
    assert not db_path.parent.exists(), "the directory must be missing for this test"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setitem(config_module.Settings.model_config, "env_file", None)
    config_module.get_settings.cache_clear()
    yield db_path
    config_module.get_settings.cache_clear()


def test_upgrade_head_creates_missing_data_directory(fresh_db_url: Path) -> None:
    command.upgrade(_alembic_config(), "head")
    assert fresh_db_url.exists(), "alembic upgrade head did not create the database"


def test_upgrade_head_creates_every_spec_18_table(fresh_db_url: Path) -> None:
    command.upgrade(_alembic_config(), "head")
    tables = _tables(fresh_db_url)
    missing = SPEC_18_TABLES - tables
    assert not missing, f"migration is missing SPEC §18 tables: {sorted(missing)}"


def test_downgrade_and_upgrade_round_trip(fresh_db_url: Path) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert not SPEC_18_TABLES & _tables(fresh_db_url)
    command.upgrade(cfg, "head")
    assert _tables(fresh_db_url) >= SPEC_18_TABLES


def test_ensure_sqlite_dir_handles_special_urls(tmp_path: Path) -> None:
    from app.db.session import ensure_sqlite_dir

    # Nested missing directories are created.
    nested = tmp_path / "a" / "b" / "c" / "vms.db"
    ensure_sqlite_dir(f"sqlite:///{nested}")
    assert nested.parent.is_dir()

    # In-memory and non-SQLite URLs are no-ops rather than errors.
    ensure_sqlite_dir("sqlite:///:memory:")
    ensure_sqlite_dir("postgresql+psycopg://user:pw@localhost/vms")
