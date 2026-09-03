"""GUI entry point (``opensubtitles-uploader-gui``).

Startup gate: the metadata account (``.env``, opensubtitles.com) is
verified against the REST API **before** the window opens.  If those
credentials are missing or wrong, the application shows the problem and
closes.  The login inside the window validates the upload account
(opensubtitles.org, XML-RPC) separately.
"""

from __future__ import annotations

import sys

from opensubtitles_uploader import __version__
from opensubtitles_uploader.adapters.ui.i18n import Translator
from opensubtitles_uploader.adapters.ui.icons import app_icon
from opensubtitles_uploader.adapters.ui.main_window import MainWindow
from opensubtitles_uploader.adapters.ui.theme import apply_theme
from opensubtitles_uploader.bootstrap import AppContext, bootstrap
from opensubtitles_uploader.config import environment_metadata_credentials


def metadata_startup_problem(ctx: AppContext, tr: Translator) -> str | None:
    """Validate the .env (opensubtitles.com) metadata account.

    Returns a human message describing the problem, or ``None`` when the
    account is configured and the REST login succeeds.
    """
    creds = environment_metadata_credentials()
    if not creds:
        return tr.tr(
            "The metadata account is missing: create a .env file with "
            "OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD "
            "(opensubtitles.com credentials)."
        )
    if not ctx.api_key.resolve():
        return tr.tr(
            "The OpenSubtitles API key is missing: set OPENSUBTITLES_API_KEY "
            "(opensubtitles.com) to validate the metadata account."
        )
    user = ctx.client.ensure_metadata_session()
    if user is None:
        detail = ctx.client.metadata_error or tr.tr("unknown error.")
        return (
            tr.tr("The metadata account could not be validated against opensubtitles.com:")
            + f"\n{detail}"
        )
    return None


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("OpenSubtitles Uploader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("anibalgh")
    app.setWindowIcon(app_icon())

    ctx = bootstrap()
    locale = str(ctx.settings.get("locale", "en") or "en")
    theme = str(ctx.settings.get("theme", "dark") or "dark")
    tr = Translator(locale)
    apply_theme(app, theme)

    problem = metadata_startup_problem(ctx, tr)
    if problem is not None:
        QMessageBox.critical(
            None,
            tr.tr("Startup check"),
            problem + "\n\n" + tr.tr("The application will close."),
        )
        return 1

    window = MainWindow(ctx, tr)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
