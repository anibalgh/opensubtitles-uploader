"""JSON-file backed settings store.

Non-secret application settings (theme, locale, last username…) live in a
single JSON file inside the platform user-config directory.  Writes are
atomic (write-temp-then-rename) so a crash cannot corrupt the file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonSettingsStore:
    """Settings persisted as ``settings.json`` under ``base_dir``."""

    def __init__(self, base_dir: Path | str, filename: str = "settings.json") -> None:
        self._file = Path(base_dir) / filename

    # -- persistence ------------------------------------------------------
    def _read(self) -> dict[str, Any]:
        try:
            raw = self._file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._file.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._file)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # -- SettingsStore protocol ------------------------------------------
    def get(self, key: str, default: object = None) -> object:
        return self._read().get(key, default)

    def set(self, key: str, value: object) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def delete(self, key: str) -> None:
        data = self._read()
        if key in data:
            del data[key]
            self._write(data)

    @property
    def file(self) -> Path:
        return self._file
