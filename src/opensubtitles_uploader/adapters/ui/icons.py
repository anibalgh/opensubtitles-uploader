"""Application icon helpers.

The artwork is the original *OpenSubtitles Uploader* icon (os-icon), kept
for continuity with the base project — it ships inside the package so it
also works when the application is frozen/installed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

ICON_DIR = Path(__file__).resolve().parents[2] / "data" / "icons"

#: Preferred runtime icon: PNG (multiplatform), ICO (Windows taskbar).
_ORDER = ("os-icon.png", "os-icon.ico", "os-icon.icns")


def icon_path() -> Path | None:
    """Return the first existing icon file (or ``None`` if missing)."""
    for name in _ORDER:
        candidate = ICON_DIR / name
        if candidate.is_file():
            return candidate
    return None


def app_icon() -> QIcon:
    """A :class:`QIcon` for the window / application, or an empty icon."""
    path = icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))


def app_pixmap(size: int = 32) -> QPixmap:
    """Square brand pixmap scaled to ``size`` (for in-window headers)."""
    path = icon_path()
    if path is None:
        return QPixmap()
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
