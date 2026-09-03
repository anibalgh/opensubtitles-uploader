"""Secret storage for credentials.

Two backends behind one factory:

- :class:`KeyringSecretStore` uses the OS keychain through the optional
  ``keyring`` package (Windows Credential Locker, macOS Keychain,
  Secret Service on Linux).
- :class:`FernetSecretStore` is the portable fallback: secrets are
  encrypted with Fernet (AES-128-CBC + HMAC) and written to a private
  file (``chmod 600``) next to the settings.  The encryption key lives in
  a separate private file in the same directory.

Credentials are **never** stored in plain text.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from opensubtitles_uploader.application.ports import SecretStore


class KeyringSecretStore:
    """OS keychain backend (requires the optional ``keyring`` package)."""

    def __init__(self, service: str = "opensubtitles-uploader") -> None:
        self._service = service

    def set_secret(self, service: str, username: str, secret: str) -> None:
        import keyring  # type: ignore[import-not-found]  # imported lazily

        keyring.set_password(service or self._service, username, secret)

    def get_secret(self, service: str, username: str) -> str | None:
        import keyring

        password = keyring.get_password(service or self._service, username)
        return password if isinstance(password, str) else None

    def delete_secret(self, service: str, username: str) -> None:
        import keyring

        with contextlib.suppress(Exception):
            keyring.delete_password(service or self._service, username)


class FernetSecretStore:
    """Encrypted local-file backend that works on any platform."""

    def __init__(self, base_dir: Path | str) -> None:
        base = Path(base_dir)
        base.mkdir(parents=True, exist_ok=True)
        self._vault_file = base / "secrets.enc"
        self._key_file = base / ".secrets.key"
        self._service = "opensubtitles-uploader"

    # -- helpers ----------------------------------------------------------
    def _load_key(self) -> bytes:
        from cryptography.fernet import Fernet

        if self._key_file.exists():
            return self._key_file.read_bytes().strip()
        key = Fernet.generate_key()
        fd = os.open(self._key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(key + b"\n")
        return key

    def _cipher(self) -> Any:
        from cryptography.fernet import Fernet

        return Fernet(self._load_key())

    def _read(self) -> dict[str, str]:
        if not self._vault_file.exists():
            return {}
        try:
            token = self._vault_file.read_bytes()
            raw = self._cipher().decrypt(token).decode("utf-8")
        except Exception:
            return {}
        import json

        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _write(self, data: dict[str, str]) -> None:
        import json

        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        token = self._cipher().encrypt(raw)
        fd = os.open(self._vault_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(token)

    # -- SecretStore protocol ---------------------------------------------
    def set_secret(self, service: str, username: str, secret: str) -> None:
        data = self._read()
        data[f"{service}:{username}"] = secret
        self._write(data)

    def get_secret(self, service: str, username: str) -> str | None:
        return self._read().get(f"{service}:{username}")

    def delete_secret(self, service: str, username: str) -> None:
        data = self._read()
        key = f"{service}:{username}"
        if key in data:
            del data[key]
            self._write(data)


def keyring_available() -> bool:
    """True when the OS keychain backend actually works here."""
    try:
        import keyring

        # Probe may fail on headless Linux (no Secret Service daemon).
        keyring.get_keyring()
        return True
    except Exception:
        return False


def build_secret_store(base_dir: Path | str) -> SecretStore:
    """Pick the best secret backend available on this machine."""
    if keyring_available():
        store = KeyringSecretStore()
        # round-trip probe against a throwaway entry
        probe = "__osu_probe__"
        try:
            store.set_secret("__osu_probe__", probe, probe)
            ok = store.get_secret("__osu_probe__", probe) == probe
            store.delete_secret("__osu_probe__", probe)
        except Exception:
            ok = False
        if ok:
            return store
    return FernetSecretStore(base_dir)
