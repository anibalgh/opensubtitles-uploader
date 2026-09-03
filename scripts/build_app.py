#!/usr/bin/env python3
"""Build distributable executables with PyInstaller.

Must be run **on each target platform** (PyInstaller does not cross-compile):

    python scripts/build_app.py gui     # "OpenSubtitlesUploader" (windowed)
    python scripts/build_app.py cli     # "opensubtitles-uploader-cli" (console)

Dependencies: ``poetry install -E build`` (adds PyInstaller).
Output: ``dist/``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = SRC / "opensubtitles_uploader" / "data"


def _icon() -> str | None:
    """Pick the icon file the current platform understands."""
    if sys.platform == "win32":
        return str(DATA / "icons" / "os-icon.ico")
    if sys.platform == "darwin":
        return str(DATA / "icons" / "os-icon.icns")
    return str(DATA / "icons" / "os-icon.png")  # informational on Linux


def _build(windowed: bool) -> int:
    import pyinstaller  # noqa: F401  # ensure the extra is installed

    name = "OpenSubtitlesUploader" if windowed else "opensubtitles-uploader-cli"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--paths",
        str(SRC),
        "--add-data",
        f"{DATA}{_sep()}opensubtitles_uploader/data",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
    ]
    if windowed:
        cmd.append("--windowed")
    icon = _icon()
    if icon and sys.platform != "linux":
        cmd += ["--icon", icon]
    if not windowed:
        cmd.append("--console")
    entry = (
        "opensubtitles_uploader.adapters.ui.main:main"
        if windowed
        else "opensubtitles_uploader.adapters.cli.main:main"
    )
    cmd.append(entry)
    print("ejecutando:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def _sep() -> str:
    return ";" if sys.platform == "win32" else ":"


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"gui", "cli"}:
        print(__doc__)
        return 2
    return _build(windowed=sys.argv[1] == "gui")


if __name__ == "__main__":
    raise SystemExit(main())
