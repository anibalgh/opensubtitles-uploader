"""PyInstaller entry point for the command-line application."""

from opensubtitles_uploader.adapters.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
