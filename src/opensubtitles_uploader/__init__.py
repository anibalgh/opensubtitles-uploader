"""OpenSubtitles Uploader.

A multiplatform desktop application that replicates the classic
*OpenSubtitles Uploader* (NW.js) flow in Python: log in to OpenSubtitles,
analyse a local video file, prepare its subtitle, and upload the subtitle —
as easy as drag & drop.

The package follows a hexagonal (ports & adapters) layout:

- ``domain``      — pure business rules (no framework / I/O imports).
- ``application`` — use cases plus the ports they depend on.
- ``adapters``    — concrete implementations (OpenSubtitles REST client,
  media probing, hashing, config/secret storage, UI and CLI drivers).
- ``bootstrap``   — composition root wiring the adapters to the core.
"""

from __future__ import annotations

__version__ = "0.1.0"

APP_NAME = "OpenSubtitles Uploader"
APP_ID = "opensubtitles-uploader"
USER_AGENT = f"OpenSubtitles-Uploader v{__version__}"
