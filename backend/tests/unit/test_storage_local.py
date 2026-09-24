"""LocalStorageProvider (SPEC §19)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.providers.storage.local import KNOWN_PREFIXES, LocalStorageProvider


def test_creates_known_prefixes(tmp_path: Path) -> None:
    LocalStorageProvider(str(tmp_path / "data"))
    for prefix in KNOWN_PREFIXES:
        assert (tmp_path / "data" / prefix).is_dir()


def test_put_get_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path))
    storage.put("evidence/evt_1/frame_0.jpg", b"\xff\xd8jpegbytes", "image/jpeg")
    assert storage.get("evidence/evt_1/frame_0.jpg") == b"\xff\xd8jpegbytes"


def test_put_creates_nested_directories(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path))
    storage.put("evidence/a/b/c/deep.json", b"{}", "application/json")
    assert (tmp_path / "evidence" / "a" / "b" / "c" / "deep.json").is_file()


def test_url_points_at_the_file(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path))
    storage.put("concepts/mug/ref0.jpg", b"x", "image/jpeg")
    assert storage.url("concepts/mug/ref0.jpg").startswith("file://")
    assert storage.url("concepts/mug/ref0.jpg").endswith("ref0.jpg")


def test_get_missing_raises(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        storage.get("evidence/nope.jpg")


def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path))
    storage.put("feedback/f1.json", b"{}", "application/json")
    storage.delete("feedback/f1.json")
    storage.delete("feedback/f1.json")  # no error the second time
    assert not storage.exists("feedback/f1.json")


@pytest.mark.parametrize(
    "key", ["../escape.txt", "evidence/../../escape.txt", "evidence/../../../etc/passwd"]
)
def test_path_traversal_blocked(tmp_path: Path, key: str) -> None:
    storage = LocalStorageProvider(str(tmp_path / "data"))
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.put(key, b"nope", "text/plain")
