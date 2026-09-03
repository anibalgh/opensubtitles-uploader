"""GUI entry point (``opensubtitles-uploader-gui``)."""

from __future__ import annotations

import sys

from opensubtitles_uploader import __version__
from opensubtitles_uploader.adapters.ui.i18n import Translator
from opensubtitles_uploader.adapters.ui.main_window import MainWindow
from opensubtitles_uploader.adapters.ui.theme import apply_theme
from opensubtitles_uploader.bootstrap import bootstrap


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("OpenSubtitles Uploader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("anibalgh")

    ctx = bootstrap()
    locale = str(ctx.settings.get("locale", "en") or "en")
    theme = str(ctx.settings.get("theme", "dark") or "dark")
    tr = Translator(locale)
    apply_theme(app, theme)

    window = MainWindow(ctx, tr)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
