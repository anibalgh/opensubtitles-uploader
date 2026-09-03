#!/usr/bin/env python3
"""Build distributable executables with PyInstaller.

Must be run **on each target platform** (PyInstaller does not cross-compile),
and with the Poetry environment (which installs PyInstaller):

    poetry install -E build
    poetry run python scripts/build_app.py gui     # "OpenSubtitlesUploader" (windowed)
    poetry run python scripts/build_app.py cli     # "opensubtitles-uploader-cli" (console)

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
    try:
        import PyInstaller  # noqa: F401  # ensure the extra is installed
    except ModuleNotFoundError:
        print(
            f"PyInstaller no está instalado en este intérprete ({sys.executable}).",
            file=sys.stderr,
        )
        print("Ejecuta primero:", file=sys.stderr)
        print("    poetry install -E build", file=sys.stderr)
        print("y después usa el entorno de Poetry:", file=sys.stderr)
        print("    poetry run python scripts/build_app.py gui", file=sys.stderr)
        return 1

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
    launcher = ROOT / "scripts" / ("launch_gui.py" if windowed else "launch_cli.py")
    cmd.append(str(launcher))
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
