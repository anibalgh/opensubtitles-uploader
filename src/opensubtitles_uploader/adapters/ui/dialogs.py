"""Reusable dialogs: title search, settings, and modal messages."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opensubtitles_uploader.adapters.media.probe import has_any_probe
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.adapters.ui.i18n import LOCALES, Translator
from opensubtitles_uploader.adapters.ui.theme import THEMES
from opensubtitles_uploader.application.ports import SettingsStore
from opensubtitles_uploader.application.services import CatalogService
from opensubtitles_uploader.domain.errors import DomainError
from opensubtitles_uploader.domain.model import MovieRef, UploadOutcome

_LANG_NAMES = {"en": "English", "es": "Español"}


class SearchDialog(QDialog):
    """Search movies/shows/episodes and pick one (returns a MovieRef)."""

    def __init__(
        self, catalog: CatalogService, tr: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._tr = tr
        self._searching = False
        self._selected: MovieRef | None = None
        self.setWindowTitle(tr.tr("Search on IMDB directly"))
        self.setModal(True)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText(tr.tr("Enter a title"))
        self._query.returnPressed.connect(self.run_search)
        self._search_btn = QPushButton(tr.tr("Search"))
        self._search_btn.setObjectName("dominant")
        self._search_btn.clicked.connect(self.run_search)
        row.addWidget(self._query, 1)
        row.addWidget(self._search_btn)
        layout.addLayout(row)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        layout.addWidget(self._status)

        self._results = QListWidget()
        self._results.itemDoubleClicked.connect(self._choose)
        self._results.itemActivated.connect(self._choose)
        layout.addWidget(self._results, 1)

        buttons = QDialogButtonBox()
        choose = buttons.addButton(tr.tr("Choose"), QDialogButtonBox.AcceptRole)
        choose.setObjectName("dominant")
        buttons.addButton(tr.tr("Close"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._choose_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._movies: list[MovieRef] = []

    # ------------------------------------------------------------------
    def run_search(self) -> None:
        query = self._query.text().strip()
        if not query or self._searching:
            return
        self._searching = True
        self._search_btn.setEnabled(False)
        self._status.setText(self._tr.tr("Searching…"))
        self._results.clear()
        self._movies = []
        try:
            results = self._catalog.search(query)
        except DomainError as exc:
            self._status.setText(self._tr.tr_code(exc.code, self._tr.tr("Not found")))
            self._search_btn.setEnabled(True)
            self._searching = False
            return
        self._movies = results
        if not results:
            self._status.setText(self._tr.tr("Not found"))
        else:
            self._status.setText(f"{len(results)} · {self._tr.tr('Search results')}")
            for movie in results:
                label = movie.display_title()
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, movie)
                self._results.addItem(item)
        self._search_btn.setEnabled(True)
        self._searching = False

    def _choose_selected(self) -> None:
        item = self._results.currentItem()
        if item is not None:
            self._choose(item)

    def _choose(self, item: QListWidgetItem) -> None:
        movie: MovieRef | None = item.data(Qt.UserRole)
        if movie is None:
            return
        self._selected = movie
        self.accept()

    @property
    def selected_movie(self) -> MovieRef | None:
        return self._selected


class SettingsDialog(QDialog):
    """Application settings (theme, locale, API key…)."""

    def __init__(
        self,
        settings: SettingsStore,
        api_key_source: ApiKeySource,
        tr: Translator,
        current_theme: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._api_key = api_key_source
        self._tr = tr
        self.setWindowTitle(tr.tr("Settings"))
        self.setModal(True)
        self.resize(420, 340)

        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)

        self._theme = QComboBox()
        for theme in THEMES:
            self._theme.addItem(tr.tr(theme.capitalize()), theme)
        self._theme.setCurrentIndex(max(0, THEMES.index(current_theme)))
        form.addRow(tr.tr("Theme"), self._theme)

        self._locale = QComboBox()
        for code in LOCALES:
            self._locale.addItem(_LANG_NAMES.get(code, code), code)
        locale = str(settings.get("locale", "en") or "en")
        self._locale.setCurrentIndex(max(0, LOCALES.index(locale) if locale in LOCALES else 0))
        form.addRow(tr.tr("Application language"), self._locale)

        self._api_key_field = QLineEdit()
        self._api_key_field.setEchoMode(QLineEdit.Password)
        stored = api_key_source.resolve() or ""
        self._api_key_field.setText(stored)
        self._api_key_field.setPlaceholderText("Api-Key · api.opensubtitles.com")
        row = QHBoxLayout()
        row.addWidget(self._api_key_field, 1)
        toggle = QPushButton("👁")
        toggle.setCheckable(True)
        toggle.clicked.connect(
            lambda checked: self._api_key_field.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        row.addWidget(toggle)
        key_widget = QWidget()
        key_widget.setLayout(row)
        form.addRow(tr.tr("OpenSubtitles API key"), key_widget)

        from opensubtitles_uploader.config import environment_metadata_credentials

        metadata = environment_metadata_credentials()
        account_label = QLabel(
            tr.tr("Metadata/search account")
            + ": "
            + (
                metadata[0]
                if metadata
                else tr.tr("not set — catalogue works with the API key alone (.env)")
            )
        )
        account_label.setObjectName("muted")
        form.addRow(account_label)
        upload_label = QLabel(
            tr.tr("Upload account") + ": " + tr.tr("the account you log in with in the main window")
        )
        upload_label.setObjectName("muted")
        form.addRow(upload_label)

        tools = tr.tr("Media info tools")
        if has_any_probe():
            tools_label = QLabel(tools + " · ✓ ffprobe/mediainfo")
        else:
            tools_label = QLabel(
                tools
                + " — "
                + tr.tr(
                    "mediainfo / ffprobe not found — fps, duration and frame count will be empty."
                )
            )
            tools_label.setWordWrap(True)
        tools_label.setObjectName("muted")
        form.addRow(tools_label)

        about = QLabel(f"OpenSubtitles Uploader · {tr.tr('developed by')} Anibal · v0.1.0")
        about.setObjectName("muted")
        form.addRow(about)

        buttons = QDialogButtonBox()
        save = buttons.addButton(tr.tr("Save"), QDialogButtonBox.AcceptRole)
        save.setObjectName("dominant")
        buttons.addButton(tr.tr("Cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    # -- read back -----------------------------------------------------
    @property
    def theme(self) -> str:
        return str(self._theme.currentData())

    @property
    def locale(self) -> str:
        return str(self._locale.currentData())

    @property
    def api_key(self) -> str:
        return self._api_key_field.text().strip()

    def save(self) -> None:
        self._settings.set("theme", self.theme)
        self._settings.set("locale", self.locale)
        self._api_key.store(self.api_key)


# ---------------------------------------------------------------------------
# Small message helpers
# ---------------------------------------------------------------------------


def confirm(parent: QWidget, tr: Translator, text: str, yes_label: str | None = None) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(tr.tr("Confirm"))
    box.setText(text)
    yes = box.addButton(yes_label or tr.tr("Yes"), QMessageBox.YesRole)
    box.addButton(tr.tr("No"), QMessageBox.NoRole)
    box.exec()
    return box.clickedButton() is yes


def upload_result_dialog(parent: QWidget, tr: Translator, outcome: UploadOutcome) -> None:
    """Result modal for a finished upload attempt."""
    box = QMessageBox(parent)
    if outcome.succeeded:
        box.setWindowTitle(tr.tr("Upload"))
        box.setText(tr.tr("Subtitle was successfully uploaded!"))
        box.setIcon(QMessageBox.Information)
        if outcome.url:
            open_btn = box.addButton(tr.tr("Open in browser"), QMessageBox.AcceptRole)
            box.addButton(tr.tr("OK"), QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl(outcome.url))
        else:
            box.addButton(tr.tr("OK"), QMessageBox.AcceptRole)
            box.exec()
        return

    if outcome.existing:
        box.setWindowTitle(tr.tr("Already present"))
        lines = [tr.tr("Subtitle was already present in the database")]
        for match in outcome.existing:
            where = ", ".join(match.matched_by) or tr.tr("movie hash")
            name = match.movie_name or match.lang_code or str(match.subtitle_id)
            lines.append(f"• {name} ({where})")
        box.setText("\n".join(lines))
        box.setIcon(QMessageBox.Warning)
        if outcome.existing[0].url:
            open_btn = box.addButton(tr.tr("Open in OpenSubtitles"), QMessageBox.AcceptRole)
            box.addButton(tr.tr("OK"), QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl(outcome.existing[0].url))
            return
        box.addButton(tr.tr("OK"), QMessageBox.AcceptRole)
        box.exec()
        return

    box.setWindowTitle(tr.tr("Error"))
    box.setText(tr.tr("upload_failed"))
    box.setIcon(QMessageBox.Critical)
    box.addButton(tr.tr("OK"), QMessageBox.AcceptRole)
    box.exec()
