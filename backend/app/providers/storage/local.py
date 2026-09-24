"""LocalStorageProvider (SPEC §19).

Only this class touches the data filesystem (CLAUDE.md hard rule #12). Rooted at
DATA_DIR with the prefixes cameras/ evidence/ concepts/ feedback/ exports/.
Keys are sanitised so they can never escape the root.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.providers.base import StorageProvider

KNOWN_PREFIXES = ("cameras", "evidence", "concepts", "feedback", "exports")


class LocalStorageProvider(StorageProvider):
    def __init__(self, data_dir: str) -> None:
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for prefix in KNOWN_PREFIXES:
            (self.root / prefix).mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        key = key.lstrip("/")
        target = (self.root / key).resolve()
        # Guard against path traversal via ../ segments.
        if os.path.commonpath([self.root, target]) != str(self.root):
            raise ValueError(f"key escapes storage root: {key!r}")
        return target

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def url(self, key: str) -> str:
        # Local provider returns a file URI; an HTTP static route can map this later.
        return self._resolve(key).as_uri()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()
