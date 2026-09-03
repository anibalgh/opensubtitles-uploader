"""API-key resolution.

The OpenSubtitles REST endpoints require an *application* ``Api-Key``.
It is read, in order: from the ``OPENSUBTITLES_API_KEY`` environment
variable (12-factor / CI / CLI) or from the secure secret store when the
user pastes it in the application Settings.
"""

from __future__ import annotations

from opensubtitles_uploader.application.ports import SecretStore
from opensubtitles_uploader.config import environment_api_key

SERVICE = "opensubtitles-uploader"
API_KEY_USERNAME = "__api_key__"


class ApiKeySource:
    def __init__(self, vault: SecretStore | None = None) -> None:
        self._vault = vault

    def resolve(self) -> str | None:
        env_value = environment_api_key()
        if env_value:
            return env_value
        if self._vault is not None:
            return self._vault.get_secret(SERVICE, API_KEY_USERNAME)
        return None

    def store(self, api_key: str) -> None:
        if self._vault is None:
            return
        if api_key.strip():
            self._vault.set_secret(SERVICE, API_KEY_USERNAME, api_key.strip())
        else:
            self._vault.delete_secret(SERVICE, API_KEY_USERNAME)
