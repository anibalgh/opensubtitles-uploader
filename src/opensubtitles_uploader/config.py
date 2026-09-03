"""Environment and user-data paths (12-factor friendly).

Only module allowed to read the environment eagerly.  Non-secret values
may be overridden by environment variables; secrets are read lazily by
the dedicated :class:`~.adapters.storage.secret_store` backend.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "opensubtitles-uploader"
APP_AUTHOR = "anibalgh"

#: OpenSubtitles REST API key — read from the environment if present.
API_KEY_ENV = "OPENSUBTITLES_API_KEY"

#: OpenSubtitles REST endpoint.
OS_BASE_URL = os.environ.get("OPENSUBTITLES_BASE_URL", "https://api.opensubtitles.com/api/v1")

#: Request timeouts (seconds).
HTTP_TIMEOUT = float(os.environ.get("OPENSUBTITLES_HTTP_TIMEOUT", "30"))


def user_config_path() -> Path:
    """Per-user settings directory (e.g. ``~/.config/opensubtitles-uploader``)."""
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def user_data_path() -> Path:
    """Per-user cache/data directory (e.g. ``~/.local/share/opensubtitles-uploader``)."""
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def environment_api_key() -> str | None:
    value = os.environ.get(API_KEY_ENV)
    return value.strip() if value and value.strip() else None
