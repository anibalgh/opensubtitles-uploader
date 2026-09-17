"""Tests for settings and secret storage backends."""

from __future__ import annotations

from cryptography.fernet import Fernet

from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.adapters.storage.secret_store import (
    FernetSecretStore,
    build_secret_store,
)
from opensubtitles_uploader.adapters.storage.settings_store import JsonSettingsStore


def test_settings_round_trip(tmp_path):
    store = JsonSettingsStore(tmp_path)
    assert store.get("theme") is None
    store.set("theme", "light")
    store.set("locale", "es")
    again = JsonSettingsStore(tmp_path)
    assert again.get("theme") == "light"
    assert again.get("locale") == "es"
    again.delete("theme")
    assert JsonSettingsStore(tmp_path).get("theme") is None


def test_settings_corrupt_file_returns_empty(tmp_path):
    file = tmp_path / "settings.json"
    file.write_text("{not json", encoding="utf-8")
    store = JsonSettingsStore(tmp_path)
    assert store.get("anything") is None


def test_fernet_secrets_round_trip(tmp_path):
    store = FernetSecretStore(tmp_path)
    store.set_secret("svc", "alice", "s3cret")
    assert store.get_secret("svc", "alice") == "s3cret"
    # A second instance must be able to read the same vault (same key file).
    assert FernetSecretStore(tmp_path).get_secret("svc", "alice") == "s3cret"
    store.delete_secret("svc", "alice")
    assert store.get_secret("svc", "alice") is None


def test_secrets_never_plaintext(tmp_path):
    store = FernetSecretStore(tmp_path)
    store.set_secret("svc", "bob", "hunter2")
    raw = (tmp_path / "secrets.enc").read_bytes()
    assert b"hunter2" not in raw
    assert b"bob" not in raw


def test_build_secret_store_fallback(tmp_path):
    store = build_secret_store(tmp_path)
    for method in ("set_secret", "get_secret", "delete_secret"):
        assert callable(getattr(store, method))
    store.set_secret("s", "u", "v")
    assert store.get_secret("s", "u") == "v"


def test_api_key_source_env_wins(monkeypatch, tmp_path):
    vault = FernetSecretStore(tmp_path)
    source = ApiKeySource(vault)
    monkeypatch.setenv("OPENSUBTITLES_API_KEY", "env-key")
    assert source.resolve() == "env-key"
    source.store("vault-key")
    monkeypatch.delenv("OPENSUBTITLES_API_KEY")
    assert source.resolve() == "vault-key"
    source.store("")
    assert source.resolve() is None


# Fernet vector produced by cryptography 45.0.7 — the version pinned before
# the security bump to 50.x.  A vault written by an older release must keep
# decrypting after the upgrade, so this fixed pair guards the wire format.
_LEGACY_FERNET_KEY = "OOB2TlcSHElGOBbqQlQcIcLDsTer1pl8x4NHj4w9nSA="
_LEGACY_FERNET_TOKEN = (
    "gAAAAABqrDBjYjPjjEJPAF-MJILVEEDc75SaCpYxn5df4zsAHjel-2GWXSdiP3h469cCXqLlXT5"
    "ObE2v4JwCpqDLOhj5jWGnfLfZyY_0rN_HusgPCJnoLN4="
)


def test_fernet_decrypts_legacy_vault():
    """Backward compatibility: tokens from cryptography 45.x decrypt on 50.x."""
    plain = Fernet(_LEGACY_FERNET_KEY.encode()).decrypt(_LEGACY_FERNET_TOKEN.encode())
    assert plain == b"legacy-vault-payload"
