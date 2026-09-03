"""Environment and user-data paths (12-factor friendly).

Only module allowed to read the environment eagerly.  Secrets are read
lazily by the dedicated :class:`~.adapters.storage.secret_store` backend.

Two credential scopes are deliberately separated:

- **metadata / catalogue account** (``OPENSUBTITLES_USERNAME`` +
  ``OPENSUBTITLES_PASSWORD``, usually in a local ``.env``): used by the
  REST catalogue (search, identification, profile).  It *never* uploads.
- **upload account** (typed in the GUI): logged in through the legacy
  XML-RPC endpoint and used only to upload subtitles.

An optional local ``.env`` file next to the project (or in the current
working directory) is loaded automatically; real environment variables
always win.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "opensubtitles-uploader"
APP_AUTHOR = "anibalgh"

#: OpenSubtitles REST API key — read from the environment if present.
API_KEY_ENV = "OPENSUBTITLES_API_KEY"

#: REST (catalogue/metadata) account — the ".env" credentials.
METADATA_USERNAME_ENV = "OPENSUBTITLES_USERNAME"
METADATA_PASSWORD_ENV = "OPENSUBTITLES_PASSWORD"

#: Optional separate credentials to test the GUI (upload) login in scripts.
UPLOAD_USERNAME_ENV = "OPENSUBTITLES_UPLOAD_USERNAME"
UPLOAD_PASSWORD_ENV = "OPENSUBTITLES_UPLOAD_PASSWORD"

#: OpenSubtitles REST endpoint.
OS_BASE_URL = os.environ.get("OPENSUBTITLES_BASE_URL", "https://api.opensubtitles.com/api/v1")

#: Request timeouts (seconds).
HTTP_TIMEOUT = float(os.environ.get("OPENSUBTITLES_HTTP_TIMEOUT", "30"))

#: Repo root (one level above the ``src`` package) — used to find ``.env``.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _dotenv_candidates() -> tuple[Path, ...]:
    return (Path.cwd() / ".env", _REPO_ROOT / ".env")


def load_dotenv() -> None:
    """Load ``KEY=VALUE`` lines from a local ``.env`` file (no override)."""
    for dotenv in _dotenv_candidates():
        if not dotenv.is_file():
            continue
        try:
            lines = dotenv.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return  # first existing file wins


def user_config_path() -> Path:
    """Per-user settings directory (e.g. ``~/.config/opensubtitles-uploader``)."""
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def user_data_path() -> Path:
    """Per-user cache/data directory (e.g. ``~/.local/share/opensubtitles-uploader``)."""
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def environment_api_key() -> str | None:
    return _env(API_KEY_ENV)


def environment_metadata_credentials() -> tuple[str, str] | None:
    """(username, password) of the REST/catalogue account, or ``None``."""
    username = _env(METADATA_USERNAME_ENV)
    password = _env(METADATA_PASSWORD_ENV)
    if not (username and password):
        return None
    return username, password


def environment_upload_credentials() -> tuple[str, str] | None:
    """Optional (username, password) to test the GUI upload login."""
    username = _env(UPLOAD_USERNAME_ENV)
    password = _env(UPLOAD_PASSWORD_ENV)
    if not (username and password):
        return None
    return username, password


# Load an optional local .env file once, at import time (real environment
# variables take precedence because load_dotenv() only sets defaults).
load_dotenv()
