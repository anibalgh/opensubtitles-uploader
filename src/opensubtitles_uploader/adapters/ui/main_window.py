"""Main window of the OpenSubtitles Uploader GUI.

Implements the desktop workflow: login, drag&drop / browse of a video and
its subtitle, automatic analysis + movie identification, metadata review
and the one-click upload — mirroring the original NW.js application.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from opensubtitles_uploader import __version__
from opensubtitles_uploader.adapters.media.dataset import bundled_languages
from opensubtitles_uploader.adapters.ui.dialogs import (
    SearchDialog,
    SettingsDialog,
    confirm,
    upload_result_dialog,
)
from opensubtitles_uploader.adapters.ui.i18n import Translator
from opensubtitles_uploader.adapters.ui.icons import app_icon, app_pixmap
from opensubtitles_uploader.adapters.ui.workers import TaskWorker
from opensubtitles_uploader.application.services import build_upload_request, normalize_imdb_id
from opensubtitles_uploader.bootstrap import AppContext
from opensubtitles_uploader.domain.errors import DomainError, ValidationError
from opensubtitles_uploader.domain.files import (
    SUBTITLE_DIALOG_PATTERN,
    VIDEO_DIALOG_PATTERN,
    classify_file,
)
from opensubtitles_uploader.domain.model import Language, MovieRef, SubtitleFile, VideoFile
from opensubtitles_uploader.domain.pairing import subtitle_matches_video


class _PosterLoader(QObject):
    """Fetches a backdrop/poster over HTTP without blocking the UI."""

    loaded = Signal(object)  # QPixmap or None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_finished)
        self._url: str | None = None

    def fetch(self, url: str | None) -> None:
        if self._url and self._manager is not None:
            pass
        self._url = url
        if not url:
            self.loaded.emit(None)
            return
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.UserAgentHeader, "OpenSubtitles-Uploader")
        self._manager.get(request)

    def _on_finished(self, reply: QNetworkReply) -> None:
        from PySide6.QtGui import QPixmap

        error = reply.error()
        data = reply.readAll() if error == QNetworkReply.NoError else None
        reply.deleteLater()
        if not data or data.isEmpty():
            self.loaded.emit(None)
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.loaded.emit(pixmap)
        else:
            self.loaded.emit(None)


class MainWindow(QMainWindow):
    """The whole application window."""

    def __init__(self, ctx: AppContext, tr: Translator) -> None:
        super().__init__()
        self.ctx = ctx
        self.tr = tr
        self._busy = False
        self._workers: list[TaskWorker] = []

        self._video: VideoFile | None = None
        self._subtitle: SubtitleFile | None = None

        self.setWindowTitle("OpenSubtitles Uploader")
        self.setWindowIcon(app_icon())
        self.resize(1080, 760)
        self.setMinimumSize(940, 640)

        self._poster = _PosterLoader(self)
        self._poster.loaded.connect(self._on_poster)

        self._languages: list[Language] = list(bundled_languages())

        self._build_ui()
        self._connect_shortcuts()
        self._apply_settings()
        self._restore_login()
        self._load_languages()
        self._refresh_startup_status()

    def _refresh_startup_status(self) -> None:
        """Show which credentials the current session will use."""
        if not self.ctx.api_key.resolve():
            self._status_message(
                self.tr.tr("Configure an OpenSubtitles API key (⚙) to enable movie search.")
            )
            return

        worker = TaskWorker(lambda: self.ctx.client.ensure_metadata_session())
        worker.succeeded.connect(self._on_metadata_ready)
        self._start_worker(worker)

    def _on_metadata_ready(self, user) -> None:
        if user is not None:
            self._status_message(
                self.tr.tr("Search account:")
                + f" {user.username} — "
                + self.tr.tr("log in above with your upload account to submit subtitles."),
                9000,
            )
        else:
            self._status_message(
                self.tr.tr(
                    "Search is ready (API key). Log in with your upload account "
                    "to submit subtitles."
                ),
                9000,
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(10)

        root.addLayout(self._build_topbar())
        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(self._build_video_card(), 5)
        cards.addWidget(self._build_subtitle_card(), 4)
        root.addLayout(cards, 1)

        self.statusBar().showMessage("")

    # -- top bar --------------------------------------------------------
    def _build_topbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        brand_icon = QLabel()
        brand_icon.setPixmap(app_pixmap(36))
        brand_icon.setFixedSize(36, 36)
        bar.addWidget(brand_icon)

        title_box = QVBoxLayout()
        title = QLabel("OpenSubtitles Uploader")
        title.setObjectName("panelTitle")
        version = QLabel(f"v{__version__} · OpenSubtitles")
        version.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(version)
        bar.addLayout(title_box)

        bar.addSpacing(12)
        bar.addStretch(1)

        # login state
        self._login_widget = QWidget()
        login_row = QHBoxLayout(self._login_widget)
        login_row.setContentsMargins(0, 0, 0, 0)
        login_row.setSpacing(6)

        upload_hint = self.tr.tr(
            "Upload account — opensubtitles.org credentials. The .env "
            "(opensubtitles.com) account is used only for metadata/search."
        )
        self._login_username = QLineEdit()
        self._login_username.setPlaceholderText(self.tr.tr("Username"))
        self._login_username.setMaximumWidth(150)
        self._login_username.setToolTip(upload_hint)
        self._login_password = QLineEdit()
        self._login_password.setPlaceholderText(self.tr.tr("Password"))
        self._login_password.setEchoMode(QLineEdit.Password)
        self._login_password.setMaximumWidth(150)
        self._login_password.setToolTip(upload_hint)
        self._login_password.returnPressed.connect(self._do_login)
        self._remember = QCheckBox(self.tr.tr("Remember me"))
        self._remember.setToolTip(upload_hint)
        self._remember.setChecked(True)
        self._login_button = QPushButton(self.tr.tr("Log in"))
        self._login_button.setToolTip(upload_hint)
        self._login_button.clicked.connect(self._do_login)

        self._login_username.returnPressed.connect(lambda: self._login_password.setFocus())
        login_row.addWidget(self._login_username)
        login_row.addWidget(self._login_password)
        login_row.addWidget(self._remember)
        login_row.addWidget(self._login_button)

        self._logged_widget = QWidget()
        logged_row = QHBoxLayout(self._logged_widget)
        logged_row.setContentsMargins(0, 0, 0, 0)
        logged_row.setSpacing(8)
        self._logged_label = QLabel()
        self._logged_label.setObjectName("badge")
        self._logout_button = QPushButton(self.tr.tr("Log out"))
        self._logout_button.setObjectName("ghost")
        self._logout_button.clicked.connect(self._do_logout)
        logged_row.addWidget(self._logged_label)
        logged_row.addWidget(self._logout_button)
        self._logged_widget.hide()
        bar.addWidget(self._login_widget)

        settings_button = QPushButton("⚙ " + self.tr.tr("Settings"))
        settings_button.setObjectName("ghost")
        settings_button.clicked.connect(self._open_settings)
        bar.addWidget(settings_button)

        self._upload_button = QPushButton(self.tr.tr("Upload"))
        self._upload_button.setObjectName("dominant")
        self._upload_button.clicked.connect(self._verify_and_upload)
        bar.addWidget(self._upload_button)
        return bar

    # -- video card ------------------------------------------------------
    def _build_video_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        self._video_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header_label = QLabel("🎬 " + self.tr.tr("Video file"))
        header_label.setObjectName("panelTitle")
        self._video_status = QLabel("")
        self._video_status.setObjectName("muted")
        reset = QPushButton("✕")
        reset.setObjectName("ghost")
        reset.setToolTip(self.tr.tr("Reset"))
        reset.setFixedWidth(28)
        reset.clicked.connect(lambda: self._reset_video())
        header.addWidget(header_label)
        header.addStretch(1)
        header.addWidget(self._video_status)
        header.addWidget(reset)
        layout.addLayout(header)

        self._drop_hint_video = QLabel(self.tr.tr("Drop a video file or select one"))
        self._drop_hint_video.setObjectName("dropZone")
        self._drop_hint_video.setAlignment(Qt.AlignCenter)
        self._drop_hint_video.setCursor(Qt.PointingHandCursor)
        self._drop_hint_video.mousePressEvent = lambda _e: self._browse_video()  # type: ignore[method-assign]
        layout.addWidget(self._drop_hint_video)

        self._movie_row = QHBoxLayout()
        self._detected_title = QLabel("")
        self._detected_title.setObjectName("panelTitle")
        self._movie_row.addWidget(self._detected_title, 1)
        self._poster_label = QLabel()
        self._poster_label.setFixedSize(0, 0)
        self._poster_label.setScaledContents(False)
        self._movie_row.addWidget(self._poster_label, 0, Qt.AlignTop)
        layout.addLayout(self._movie_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setSpacing(6)

        self.video_name = QLineEdit()
        self.video_name.setReadOnly(True)
        self.video_hash = QLineEdit()
        self.video_hash.setReadOnly(True)
        self.video_size = QLineEdit()
        self.video_size.setReadOnly(True)

        self.imdb_field = QLineEdit()
        self.imdb_field.setPlaceholderText("tt1234567")
        imdb_row = QHBoxLayout()
        search_btn = QPushButton("🔍")
        search_btn.setObjectName("ghost")
        search_btn.setToolTip(self.tr.tr("Search on IMDB directly"))
        search_btn.clicked.connect(self._open_search)
        imdb_row.addWidget(self.imdb_field, 1)
        imdb_row.addWidget(search_btn)
        imdb_widget = QWidget()
        imdb_widget.setLayout(imdb_row)

        self.hd_check = QCheckBox(self.tr.tr("High definition"))

        self.video_aka = QLineEdit()
        self.video_release = QLineEdit()
        self.video_fps = QLineEdit()
        self.video_duration = QLineEdit()
        self.video_duration.setReadOnly(True)
        self.video_frames = QLineEdit()
        self.video_frames.setReadOnly(True)

        form.addRow(self.tr.tr("File name"), self.video_name)
        form.addRow(self.tr.tr("OSDb Hash"), self.video_hash)
        form.addRow(self.tr.tr("Size") + " (" + self.tr.tr("bytes") + ")", self.video_size)
        form.addRow(self.tr.tr("IMDB id"), imdb_widget)
        form.addRow("", self.hd_check)
        form.addRow(self.tr.tr("Movie AKA"), self.video_aka)
        form.addRow(self.tr.tr("Release name"), self.video_release)
        form.addRow("FPS", self.video_fps)
        form.addRow(self.tr.tr("Total time") + " (ms)", self.video_duration)
        form.addRow(self.tr.tr("Number of frames"), self.video_frames)
        layout.addLayout(form)
        layout.addStretch(1)
        return card

    # -- subtitle card ----------------------------------------------------
    def _build_subtitle_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        self._subtitle_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header_label = QLabel("💬 " + self.tr.tr("Subtitle file"))
        header_label.setObjectName("panelTitle")
        self._subtitle_status = QLabel("")
        self._subtitle_status.setObjectName("muted")
        reset = QPushButton("✕")
        reset.setObjectName("ghost")
        reset.setFixedWidth(28)
        reset.setToolTip(self.tr.tr("Reset"))
        reset.clicked.connect(lambda: self._reset_subtitle())
        header.addWidget(header_label)
        header.addStretch(1)
        header.addWidget(self._subtitle_status)
        header.addWidget(reset)
        layout.addLayout(header)

        self._drop_hint_subtitle = QLabel(self.tr.tr("Drop a subtitle file or select one"))
        self._drop_hint_subtitle.setObjectName("dropZone")
        self._drop_hint_subtitle.setAlignment(Qt.AlignCenter)
        self._drop_hint_subtitle.setCursor(Qt.PointingHandCursor)
        self._drop_hint_subtitle.mousePressEvent = lambda _e: self._browse_subtitle()  # type: ignore[method-assign]
        layout.addWidget(self._drop_hint_subtitle)

        flags = QHBoxLayout()
        self.sub_hearing = QCheckBox(self.tr.tr("Hearing impaired"))
        self.sub_machine = QCheckBox(self.tr.tr("Auto-translated"))
        self.sub_foreign = QCheckBox(self.tr.tr("Foreign parts only"))
        flags.addWidget(self.sub_hearing)
        flags.addWidget(self.sub_machine)
        flags.addWidget(self.sub_foreign)
        layout.addLayout(flags)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setSpacing(6)

        self.sub_name = QLineEdit()
        self.sub_name.setReadOnly(True)
        self.sub_md5 = QLineEdit()
        self.sub_md5.setReadOnly(True)

        lang_row = QHBoxLayout()
        self.sub_language = QComboBox()
        self.sub_language.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lang_row.addWidget(self.sub_language, 1)
        detect_btn = QPushButton("✨")
        detect_btn.setObjectName("ghost")
        detect_btn.setToolTip(self.tr.tr("Auto-detect the language"))
        detect_btn.clicked.connect(self._redetect_subtitle_language)
        lang_row.addWidget(detect_btn)
        lang_widget = QWidget()
        lang_widget.setLayout(lang_row)

        self.sub_translator = QLineEdit()
        self.sub_comment = QTextEdit()
        self.sub_comment.setFixedHeight(64)
        self.sub_comment.setAcceptRichText(False)

        form.addRow(self.tr.tr("File name"), self.sub_name)
        form.addRow("MD5", self.sub_md5)
        form.addRow(self.tr.tr("Language"), lang_widget)
        form.addRow(self.tr.tr("Translator"), self.sub_translator)
        form.addRow(self.tr.tr("Comment"), self.sub_comment)
        layout.addLayout(form)
        layout.addStretch(1)
        return card

    def _connect_shortcuts(self) -> None:
        open_files = QShortcut(QKeySequence("Ctrl+O"), self)
        open_files.activated.connect(self._browse_files)
        clear = QShortcut(QKeySequence("Ctrl+W"), self)
        clear.activated.connect(self._reset_all)
        upload = QShortcut(QKeySequence("Ctrl+Return"), self)
        upload.activated.connect(self._verify_and_upload)
        search = QShortcut(QKeySequence("Ctrl+F"), self)
        search.activated.connect(self._open_search)

    # ------------------------------------------------------------------
    # Settings & startup
    # ------------------------------------------------------------------
    def _apply_settings(self) -> None:
        locale = str(self.ctx.settings.get("locale", "en") or "en")
        theme = str(self.ctx.settings.get("theme", "dark") or "dark")
        if locale != self.tr.locale:
            self.tr = Translator(locale)
        from opensubtitles_uploader.adapters.ui.theme import apply_theme

        apply_theme(QApplication.instance(), theme)

    def _restore_login(self) -> None:
        remembered = self.ctx.auth.remembered_username
        if remembered:
            self._login_username.setText(remembered)
        if self.ctx.settings.get("os_refreshed"):
            self._login_password.setPlaceholderText("••••••••")

    def _load_languages(self) -> None:
        """Fill the language dropdown (offline list first, then refresh)."""
        self._fill_language_combo(self._languages)

        def load() -> list[Language]:
            return self.ctx.languages()

        worker = TaskWorker(load)
        worker.succeeded.connect(self._on_languages)
        self._start_worker(worker)

    def _fill_language_combo(self, languages: list[Language]) -> None:
        self.sub_language.clear()
        self.sub_language.addItem(self.tr.tr("None"), None)
        for language in languages:
            self.sub_language.addItem(f"{language.display()}", language)

    def _on_languages(self, languages: list[Language]) -> None:
        if not languages:
            return
        self._languages = languages
        self._fill_language_combo(languages)
        if self._subtitle is not None:
            self._select_language(self._subtitle.language)

    # ------------------------------------------------------------------
    # busy helpers
    # ------------------------------------------------------------------
    def _start_worker(self, worker: TaskWorker) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker))
        worker.start()

    def _busy_indicator(self, on: bool, text: str = "") -> None:
        self._busy = on
        self._upload_button.setEnabled(not on)
        if text:
            self._status_message(text)

    def _status_message(self, text: str, timeout: int = 6000) -> None:
        self.statusBar().showMessage(text, timeout)

    def _on_task_error(self, exc: Exception) -> None:
        self._busy_indicator(False)
        self._status_message(self._friendly_error(exc))

    # ------------------------------------------------------------------
    # file input: dialogs + drag&drop
    # ------------------------------------------------------------------
    def _browse_video(self) -> None:
        filters = self.tr.tr("Video files") + f" ({VIDEO_DIALOG_PATTERN})"
        path, _ = QFileDialog.getOpenFileName(self, self.tr.tr("Video file"), "", filters)
        if path:
            self.load_video(path)

    def _browse_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr.tr("Subtitle file"),
            "",
            self.tr.tr("Subtitle files") + f" ({SUBTITLE_DIALOG_PATTERN})",
        )
        if path:
            self.load_subtitle(path)

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, self.tr.tr("Import file(s)"))
        if not paths:
            return
        self._load_dropped([Path(p) for p in paths])

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile()
        ]
        self._load_dropped(paths)
        event.acceptProposedAction()

    def _load_dropped(self, paths: list[Path]) -> None:
        video: Path | None = None
        subtitle: Path | None = None
        unsupported = 0
        for path in paths:
            kind = classify_file(path.name)
            if kind == "video" and video is None:
                video = path
            elif kind == "subtitle" and subtitle is None:
                subtitle = path
            else:
                unsupported += 1
        if unsupported and not video and not subtitle:
            self._status_message(self.tr.tr("Dropped file is not supported"))
            return
        multidrop = video is not None and subtitle is not None
        if video is not None:
            self.load_video(str(video), multidrop=multidrop)
        if subtitle is not None:
            self.load_subtitle(str(subtitle), multidrop=multidrop)

    # ------------------------------------------------------------------
    # video workflow
    # ------------------------------------------------------------------
    def load_video(self, path: str, multidrop: bool = False) -> None:
        if self._busy:
            self._status_message(self.tr.tr("Please wait for the current task…"))
            return
        self._busy_indicator(True)
        self._video_status.setText(self.tr.tr("Analysing video…"))

        def task() -> VideoFile:
            video = self.ctx.videos.analyze(path)
            return self.ctx.videos.identify(video)

        worker = TaskWorker(task)
        worker.succeeded.connect(lambda video: self._on_video_analysed(video, multidrop))
        worker.failed.connect(self._on_video_failed)
        self._start_worker(worker)

    def _on_video_failed(self, exc: Exception) -> None:
        self._busy_indicator(False)
        self._video_status.setText("")
        self._status_message(self._friendly_error(exc))

    def _on_video_analysed(self, video: VideoFile, multidrop: bool) -> None:
        self._busy_indicator(False)
        self._video_status.setText(self.tr.tr("Video imported"))
        self._video = video
        self._populate_video(video)
        if not multidrop:
            self._auto_pair_subtitle(video)

    def _populate_video(self, video: VideoFile) -> None:
        self.video_name.setText(video.name)
        self.video_hash.setText(video.os_hash)
        self.video_size.setText(f"{video.size_bytes}")
        self.video_fps.setText(str(video.media.frame_rate) if video.media.frame_rate else "")
        self.video_duration.setText(str(video.media.duration_ms) if video.media.duration_ms else "")
        self.video_frames.setText(str(video.media.frame_count) if video.media.frame_count else "")
        self.video_aka.setText("")
        self.video_release.setText("")
        self.hd_check.setChecked(video.hd)
        self._drop_hint_video.hide()
        self._set_movie(video.movie)
        self._video_status.setText("")

    def _set_movie(self, movie: MovieRef | None) -> None:
        if movie is None:
            self._detected_title.setText("")
            self.imdb_field.setText("")
            self._poster_label.setFixedSize(0, 0)
            self._poster_label.clear()
            return
        self.imdb_field.setText(movie.imdb_id)
        self._detected_title.setText(movie.display_title())
        if self._video is not None and movie.imdb_id:
            self._video = VideoFile(
                path=self._video.path,
                name=self._video.name,
                size_bytes=self._video.size_bytes,
                os_hash=self._video.os_hash,
                media=self._video.media,
                movie=movie,
            )
        self._poster.fetch(movie.backdrop_url)

    def _on_poster(self, pixmap) -> None:
        if pixmap is None or pixmap.isNull():
            self._poster_label.setFixedSize(0, 0)
            return
        scaled = pixmap.scaledToWidth(160)
        self._poster_label.setPixmap(scaled)
        self._poster_label.setFixedSize(scaled.size())

    def _auto_pair_subtitle(self, video: VideoFile) -> None:
        try:
            siblings = [p for p in video.path.parent.iterdir() if p.is_file()]
        except OSError:
            return
        candidates = [
            p
            for p in siblings
            if classify_file(p.name) == "subtitle" and subtitle_matches_video(p.name, video.name)
        ]
        if not candidates:
            return
        candidate = candidates[0]
        if (
            self._subtitle is not None
            and self._subtitle.path != candidate
            and not confirm(
                self,
                self.tr,
                self.tr.tr("Replace the currently loaded file with the detected one")
                + f"\n\n{candidate.name}",
            )
        ):
            return
        self.load_subtitle(str(candidate), multidrop=True)

    # ------------------------------------------------------------------
    # subtitle workflow
    # ------------------------------------------------------------------
    def load_subtitle(self, path: str, multidrop: bool = False) -> None:
        if self._busy:
            self._status_message(self.tr.tr("Please wait for the current task…"))
            return
        self._busy_indicator(True)
        self._subtitle_status.setText(self.tr.tr("Analysing subtitle…"))

        worker = TaskWorker(lambda: self.ctx.subtitles.analyze(path))
        worker.succeeded.connect(lambda sub: self._on_subtitle_analysed(sub, multidrop))
        worker.failed.connect(self._on_subtitle_failed)
        self._start_worker(worker)

    def _on_subtitle_failed(self, exc: Exception) -> None:
        self._busy_indicator(False)
        self._subtitle_status.setText("")
        self._status_message(self._friendly_error(exc))

    def _on_subtitle_analysed(self, subtitle: SubtitleFile, multidrop: bool) -> None:
        self._busy_indicator(False)
        self._subtitle_status.setText(self.tr.tr("Subtitle imported"))
        self._subtitle = subtitle
        self.sub_name.setText(subtitle.name)
        self.sub_md5.setText(subtitle.md5)
        self.sub_hearing.setChecked(subtitle.hearing_impaired)
        self.sub_machine.setChecked(subtitle.machine_translated)
        self.sub_foreign.setChecked(subtitle.foreign_parts_only)
        self.sub_translator.setText("")
        self.sub_comment.clear()
        self._select_language(subtitle.language)
        self._drop_hint_subtitle.hide()
        if not multidrop:
            self._auto_pair_video(subtitle)

    def _select_language(self, language: Language | None) -> None:
        for index in range(self.sub_language.count()):
            candidate = self.sub_language.itemData(index)
            if candidate is None:
                continue
            if language is not None and (
                candidate.iso639_1 == language.iso639_1 or candidate.code == language.code
            ):
                self.sub_language.setCurrentIndex(index)
                return
        self.sub_language.setCurrentIndex(0)

    def _redetect_subtitle_language(self) -> None:
        if self._subtitle is None:
            return
        worker = TaskWorker(lambda: self.ctx.subtitles.analyze(str(self._subtitle.path)))
        worker.succeeded.connect(lambda sub: self._select_language(sub.language))
        worker.failed.connect(lambda exc: self._status_message(self._friendly_error(exc)))
        self._start_worker(worker)

    def _auto_pair_video(self, subtitle: SubtitleFile) -> None:
        try:
            siblings = [p for p in subtitle.path.parent.iterdir() if p.is_file()]
        except OSError:
            return
        candidates = [
            p
            for p in siblings
            if classify_file(p.name) == "video" and subtitle_matches_video(subtitle.name, p.name)
        ]
        if not candidates:
            return
        candidate = candidates[0]
        if (
            self._video is not None
            and self._video.path != candidate
            and not confirm(
                self,
                self.tr,
                self.tr.tr("Replace the currently loaded file with the detected one")
                + f"\n\n{candidate.name}",
            )
        ):
            return
        self.load_video(str(candidate), multidrop=True)

    # ------------------------------------------------------------------
    # movie search / imdb
    # ------------------------------------------------------------------
    def _open_search(self) -> None:
        dialog = SearchDialog(self.ctx.catalog, self.tr, self)
        if self._video is not None:
            dialog._query.setText(self.ctx.videos.search_query_hint(self._video))
        if dialog.exec():
            movie = dialog.selected_movie
            if movie is not None:
                self._set_movie(movie)

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------
    def _reset_video(self) -> None:
        self._video = None
        for field in (
            self.video_name,
            self.video_hash,
            self.video_size,
            self.video_fps,
            self.video_duration,
            self.video_frames,
            self.video_aka,
            self.video_release,
            self.imdb_field,
        ):
            field.clear()
        self.hd_check.setChecked(False)
        self._detected_title.clear()
        self._poster_label.setFixedSize(0, 0)
        self._poster_label.clear()
        self._drop_hint_video.show()

    def _reset_subtitle(self) -> None:
        self._subtitle = None
        for field in (self.sub_name, self.sub_md5, self.sub_translator):
            field.clear()
        self.sub_comment.clear()
        for box in (self.sub_hearing, self.sub_machine, self.sub_foreign):
            box.setChecked(False)
        self.sub_language.setCurrentIndex(0)
        self._drop_hint_subtitle.show()

    def _reset_all(self) -> None:
        self._reset_video()
        self._reset_subtitle()

    # ------------------------------------------------------------------
    # login
    # ------------------------------------------------------------------
    def _do_login(self) -> None:
        username = self._login_username.text().strip()
        password = self._login_password.text()
        if not username or not password:
            code = "username_required" if not username else "password_required"
            self._status_message(self.tr.tr_code(code, code))
            return
        self._login_button.setEnabled(False)
        self._login_button.setText("…")
        worker = TaskWorker(
            lambda: self.ctx.auth.login(username, password, remember=self._remember.isChecked())
        )
        worker.succeeded.connect(self._on_logged_in)
        worker.failed.connect(self._on_login_failed)
        self._start_worker(worker)

    def _friendly_error(self, exc: Exception) -> str:
        """A human, translated error message without raw codes/prefixes."""
        if isinstance(exc, DomainError):
            code, fallback = exc.code, exc.message
        else:
            code, fallback = "generic_error", str(exc)
        return self.tr.tr_code(code, fallback)

    def _on_login_failed(self, exc: Exception) -> None:
        self._login_button.setEnabled(True)
        self._login_button.setText(self.tr.tr("Log in"))
        text = self._friendly_error(exc)
        self._status_message(text, 12000)
        # A modal makes a failed login impossible to miss.
        QMessageBox.warning(self, self.tr.tr("Log in"), text)

    def _on_logged_in(self, user) -> None:
        self._login_button.setEnabled(True)
        self._login_button.setText(self.tr.tr("Log in"))
        self._logged_label.setText("👤 " + user.username)
        self._login_widget.hide()
        self._logged_widget.show()
        if not getattr(user, "upload_capable", True):
            self._status_message(
                self.tr.tr(
                    "Uploads need a legacy opensubtitles.org account — this "
                    "opensubtitles.com login works for search but not for uploading."
                ),
                9000,
            )
        else:
            self._status_message(self.tr.tr("Logged in as") + f" {user.username}")

    def _do_logout(self) -> None:
        self.ctx.auth.logout()
        self._login_password.clear()
        self._logged_widget.hide()
        self._login_widget.show()
        self._status_message(self.tr.tr("Log out"))

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        current_theme = str(self.ctx.settings.get("theme", "dark") or "dark")
        dialog = SettingsDialog(self.ctx.settings, self.ctx.api_key, self.tr, current_theme, self)
        if dialog.exec():
            locale_changed = dialog.locale != self.tr.locale
            theme_changed = dialog.theme != current_theme
            dialog.save()
            if theme_changed:
                from opensubtitles_uploader.adapters.ui.theme import apply_theme

                apply_theme(QApplication.instance(), dialog.theme)
            if locale_changed:
                self.tr = Translator(dialog.locale)
                self._status_message("✓")

    # ------------------------------------------------------------------
    # upload
    # ------------------------------------------------------------------
    def _typed_imdb_id(self) -> str | None:
        """Manually typed IMDB id, normalized to ``tt...`` (or ``None``).

        Raises :class:`ValidationError` when the field is non-empty but invalid.
        """
        text = self.imdb_field.text().strip()
        if not text:
            return None
        return normalize_imdb_id(text)

    @staticmethod
    def _apply_imdb(video: VideoFile, imdb_id: str) -> VideoFile:
        movie = video.movie
        if movie is None:
            movie = MovieRef(imdb_id=imdb_id, title="")
        else:
            movie = replace(movie, imdb_id=imdb_id)
        return replace(video, movie=movie)

    def _verify_and_upload(self) -> None:
        if self._busy:
            return
        if self._subtitle is None:
            self._status_message(self.tr.tr("Drop a subtitle file or select one"))
            return
        if self._video is None:
            self._status_message(self.tr.tr("Drop a video file or select one"))
            return
        try:
            typed = self._typed_imdb_id()
        except ValidationError:
            text = self.tr.tr_code("imdb_id_invalid", self.tr.tr("IMDB id"))
            self._status_message(text, 8000)
            QMessageBox.warning(self, self.tr.tr("Upload"), text)
            return
        if typed is None and self._video.movie is None:
            box = QMessageBox(self)
            box.setWindowTitle(self.tr.tr("Upload"))
            box.setText(self.tr.tr_code("imdb_id_required", self.tr.tr("Upload")))
            edit = box.addButton(self.tr.tr("Edit"), QMessageBox.AcceptRole)
            upload_now = box.addButton(self.tr.tr("Upload now"), QMessageBox.AcceptRole)
            box.addButton(self.tr.tr("Cancel"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is edit:
                self._open_search()
                return
            if box.clickedButton() is not upload_now:
                return
        self._run_upload(typed)

    def _run_upload(self, typed_imdb: str | None = None) -> None:
        language: Language | None = self.sub_language.currentData()
        if language is None:
            self._status_message(self.tr.tr("language_required"))
            return
        if self._video is None or self._subtitle is None:
            return
        video = self._video
        if typed_imdb and (video.movie is None or video.movie.imdb_id != typed_imdb):
            video = self._apply_imdb(video, typed_imdb)

        request = build_upload_request(
            video,
            self._subtitle,
            language=language,
            movie_aka=self.video_aka.text(),
            release_name=self.video_release.text(),
            high_definition=self.hd_check.isChecked(),
            translator=self.sub_translator.text(),
            comment=self.sub_comment.toPlainText(),
            hearing_impaired=self.sub_hearing.isChecked(),
            machine_translated=self.sub_machine.isChecked(),
            foreign_parts_only=self.sub_foreign.isChecked(),
        )
        self._busy_indicator(True, self.tr.tr("Uploading…"))
        worker = TaskWorker(lambda: self.ctx.uploads.upload(request))
        worker.succeeded.connect(self._on_upload_done)
        worker.failed.connect(self._on_upload_failed)
        self._start_worker(worker)

    def _on_upload_done(self, outcome) -> None:
        self._busy_indicator(False)
        upload_result_dialog(self, self.tr, outcome)
        if outcome.succeeded:
            self._reset_all()

    def _on_upload_failed(self, exc: Exception) -> None:
        self._busy_indicator(False)
        text = self._friendly_error(exc)
        self._status_message(text, 12000)
        # A modal makes the upload failure (and its reason) impossible to miss.
        if isinstance(exc, DomainError):
            detail = exc.message if hasattr(exc, "message") else None
            if detail and detail != text:
                text = f"{text}\n\n{detail}"
        box = QMessageBox(self)
        box.setWindowTitle(self.tr.tr("Upload"))
        box.setIcon(QMessageBox.Critical)
        box.setText(text)
        if isinstance(exc, DomainError) and exc.code == "upload_account_required":
            box.setInformativeText(
                self.tr.tr("Log in above with your opensubtitles.org account to upload.")
            )
        box.addButton(self.tr.tr("OK"), QMessageBox.AcceptRole)
        box.exec()

    # ------------------------------------------------------------------
    # close
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(2000)
        event.accept()
