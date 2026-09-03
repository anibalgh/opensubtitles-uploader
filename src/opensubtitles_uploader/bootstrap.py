"""Composition root.

The only place that imports concrete adapters together with the core and
wires them.  Both the GUI and the CLI bootstrap from here; tests may
build their own contexts with fakes instead.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path

from opensubtitles_uploader.adapters.media.dataset import bundled_languages
from opensubtitles_uploader.adapters.media.hashing import LocalFileHasher
from opensubtitles_uploader.adapters.media.language_detector import HeuristicLanguageDetector
from opensubtitles_uploader.adapters.media.probe import CommandLineMediaProbe
from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.adapters.storage.secret_store import build_secret_store
from opensubtitles_uploader.adapters.storage.settings_store import JsonSettingsStore
from opensubtitles_uploader.application.ports import SecretStore, SettingsStore
from opensubtitles_uploader.application.services import (
    AuthService,
    CatalogService,
    SubtitleService,
    UploadService,
    VideoService,
)
from opensubtitles_uploader.config import user_config_path
from opensubtitles_uploader.domain.model import Language


@dataclass
class AppContext:
    """Everything a driving adapter (GUI/CLI) needs."""

    settings: SettingsStore
    vault: SecretStore
    api_key: ApiKeySource
    client: OpenSubtitlesClient
    auth: AuthService
    catalog: CatalogService
    videos: VideoService
    subtitles: SubtitleService
    uploads: UploadService
    config_dir: Path = field(default_factory=user_config_path)

    def languages(self) -> list[Language]:
        """Subtitle-language catalogue for dropdowns (offline safe)."""
        with contextlib.suppress(Exception):
            online = self.client.languages()
            if online:
                return online
        return list(bundled_languages())


def bootstrap(config_dir: Path | None = None, *, user_agent: str | None = None) -> AppContext:
    """Wire real adapters into the application services."""
    base_dir = Path(config_dir) if config_dir else user_config_path()
    settings = JsonSettingsStore(base_dir)
    vault = build_secret_store(base_dir)
    api_key = ApiKeySource(vault)
    client = OpenSubtitlesClient(api_key=api_key, user_agent=user_agent or "OpenSubtitles-Uploader")
    return AppContext(
        settings=settings,
        vault=vault,
        api_key=api_key,
        client=client,
        auth=AuthService(client, vault, settings),
        catalog=CatalogService(client),
        videos=VideoService(LocalFileHasher(), CommandLineMediaProbe(), client),
        subtitles=SubtitleService(LocalFileHasher(), HeuristicLanguageDetector()),
        uploads=UploadService(client, client),
        config_dir=base_dir,
    )
