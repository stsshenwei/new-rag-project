from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class ObjectStorageProvider(Protocol):
    def put(self, data: bytes, *, suffix: str = "", prefix: str = "media") -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalObjectStorage:
    def __init__(self, root: str | Path, max_object_bytes: int = 25 * 1024 * 1024):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_object_bytes = max_object_bytes

    def put(self, data: bytes, *, suffix: str = "", prefix: str = "media") -> str:
        if len(data) > self.max_object_bytes:
            raise ValueError("Object exceeds configured size limit")
        safe_prefix = re.sub(r"[^a-zA-Z0-9_/-]", "-", prefix).strip("/") or "media"
        safe_suffix = re.sub(r"[^a-zA-Z0-9.]", "", suffix.lower())
        if safe_suffix and not safe_suffix.startswith("."):
            safe_suffix = "." + safe_suffix
        key = f"{safe_prefix}/{uuid4().hex}{safe_suffix}"
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        if target.exists():
            target.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def clear_all(self) -> None:
        for item in sorted(self.root.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                try: item.rmdir()
                except OSError: pass

    def _resolve(self, key: str) -> Path:
        if not key or Path(key).is_absolute():
            raise ValueError("Invalid object key")
        target = (self.root / key).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Object key escapes storage root") from exc
        return target
