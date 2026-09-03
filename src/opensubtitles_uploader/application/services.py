"""Application services (use cases).

Each service is a plain class wired at the composition root with the
ports it needs.  Services orchestrate domain rules and return pure data;
they never talk to HTTP, disk or UI directly.
"""

from __future__ import annotations

import re
from pathlib import Path

from opensubtitles_uploader.application.ports import (
    BackdropProvider,
    FileHasher,
    LanguageDetector,
    MediaProbe,
    OpenSubtitlesAuth,
    OpenSubtitlesCatalog,
    OpenSubtitlesUploader,
    SecretStore,
    SettingsStore,
)
from opensubtitles_uploader.domain.errors import (
    FileNotFoundError_,
    FileNotSupportedError,
    ValidationError,
)
from opensubtitles_uploader.domain.files import (
    classify_file,
    has_foreign_only_markers,
    has_machine_translation_markers,
    likely_hearing_impaired,
)
from opensubtitles_uploader.domain.model import (
    Language,
    MovieRef,
    SubtitleFile,
    UploadOutcome,
    UploadRequest,
    UserInfo,
    VideoFile,
)
from opensubtitles_uploader.domain.naming import clean_movie_name, significant_words

_IMDB_ID_RE = re.compile(r"^(?:tt?)?\d{1,9}$", re.IGNORECASE)


def normalize_imdb_id(value: str) -> str:
    """Normalise user input (``1234``, ``tt1234``, ``tt1234567/``…)."""
    text = value.strip()
    if not text:
        raise ValidationError("An IMDB id is required.", code="imdb_id_required")
    text = text.rstrip("/")
    text = text.replace("http://www.imdb.com/title/", "").replace("https://www.imdb.com/title/", "")
    if not _IMDB_ID_RE.match(text):
        raise ValidationError("The IMDB id looks invalid.", code="imdb_id_invalid")
    return "tt" + text.lower().lstrip("t")


def _ensure_readable_file(path: Path, kind: str | None) -> Path:
    if not path.exists():
        raise FileNotFoundError_(f"{path} does not exist.")
    if not path.is_file():
        raise FileNotSupportedError(f"{path} is not a file.")
    detected = classify_file(path)
    if kind and detected != kind:
        raise FileNotSupportedError(
            f"{path.name} is not a supported {kind} file.", code="file_not_supported"
        )
    return path


class AuthService:
    """Login / logout / session persistence for OpenSubtitles."""

    _SERVICE = "opensubtitles-uploader"

    def __init__(
        self,
        auth: OpenSubtitlesAuth,
        vault: SecretStore,
        settings: SettingsStore,
    ) -> None:
        self._auth = auth
        self._vault = vault
        self._settings = settings

    @property
    def remembered_username(self) -> str | None:
        value = self._settings.get("os_user")
        return str(value) if value else None

    def login(self, username: str, password: str, remember: bool = True) -> UserInfo:
        if not username.strip():
            raise ValidationError("Username cannot be empty.", code="username_required")
        if not password:
            raise ValidationError("Password cannot be empty.", code="password_required")
        session = self._auth.login(username, password)
        self._settings.set("os_user", username)
        if remember:
            self._vault.set_secret(self._SERVICE, username, password)
        else:
            self._vault.delete_secret(self._SERVICE, username)
        return session.user

    def restore(self) -> UserInfo | None:
        """Restore a session from the previous run, if credentials exist."""
        username = self.remembered_username
        if not username:
            return None
        password = self._vault.get_secret(self._SERVICE, username)
        if not password:
            return None
        try:
            return self.login(username, password, remember=True)
        except Exception:
            return None

    def logout(self) -> None:
        username = self.remembered_username
        if username:
            self._vault.delete_secret(self._SERVICE, username)
        self._settings.delete("os_user")


class CatalogService:
    """Movie search / details used by the UI."""

    def __init__(
        self,
        catalog: OpenSubtitlesCatalog,
        backdrop: BackdropProvider | None = None,
    ) -> None:
        self._catalog = catalog
        self._backdrop = backdrop

    def search(self, query: str) -> list[MovieRef]:
        query = query.strip()
        if not query:
            raise ValidationError("Search query cannot be empty.", code="search_query_required")
        return self._catalog.search_features(query)

    def details(self, imdb_id: str) -> MovieRef | None:
        return self._catalog.feature_details(normalize_imdb_id(imdb_id))

    def attach_backdrop(self, movie: MovieRef) -> MovieRef:
        if self._backdrop is None or movie.backdrop_url:
            return movie
        url = self._backdrop.get_backdrop(movie)
        if not url:
            return movie
        return MovieRef(
            imdb_id=movie.imdb_id,
            title=movie.title,
            year=movie.year,
            kind=movie.kind,
            season=movie.season,
            episode=movie.episode,
            backdrop_url=url,
        )


class VideoService:
    """Analyse a local video file and try to identify the movie."""

    def __init__(
        self,
        hasher: FileHasher,
        probe: MediaProbe,
        catalog: OpenSubtitlesCatalog,
        backdrop: BackdropProvider | None = None,
    ) -> None:
        self._hasher = hasher
        self._probe = probe
        self._catalog = catalog
        self._backdrop = backdrop

    def analyze(self, path: str | Path) -> VideoFile:
        file = _ensure_readable_file(Path(path), "video")
        moviehash, size = self._hasher.movie_hash(file)
        media = self._probe.probe(file)
        movie: MovieRef | None = None
        # If the service knows the hash, we already have our answer.
        try:
            movie = self._catalog.identify(moviehash, size)
        except Exception:
            movie = None  # identification is best-effort
        return VideoFile(
            path=file,
            name=file.name,
            size_bytes=size,
            os_hash=moviehash,
            media=media,
            movie=movie,
        )

    def identify(self, video: VideoFile) -> VideoFile:
        """Best-effort movie identification, mirroring the old flow.

        1. the hash match already found by :meth:`analyze`; otherwise
        2. a ``GuessMovieFromString``-style guess on the file name;
        3. fall back to a full-text search using the cleaned file name.
        """
        movie = video.movie
        if movie is None:
            try:
                movie = self._catalog.guess_movie(video.name)
            except Exception:
                movie = None
        if movie is None:
            title = clean_movie_name(video.name)
            if title:
                try:
                    results = self._catalog.search_features(title)
                    movie = results[0] if results else None
                except Exception:
                    movie = None
        if movie is None:
            return video
        return self._apply_movie(video, movie)

    def attach_backdrop(self, video: VideoFile) -> VideoFile:
        if self._backdrop is None or video.movie is None:
            return video
        return self._apply_movie(video, video.movie)

    def _apply_movie(self, video: VideoFile, movie: MovieRef) -> VideoFile:
        backdrop = movie.backdrop_url
        if backdrop is None and self._backdrop is not None:
            backdrop = self._backdrop.get_backdrop(movie)
        if backdrop:
            movie = MovieRef(
                imdb_id=movie.imdb_id,
                title=movie.title,
                year=movie.year,
                kind=movie.kind,
                season=movie.season,
                episode=movie.episode,
                backdrop_url=backdrop,
            )
        return VideoFile(
            path=video.path,
            name=video.name,
            size_bytes=video.size_bytes,
            os_hash=video.os_hash,
            media=video.media,
            movie=movie,
        )

    def search_query_hint(self, video: VideoFile) -> str:
        words = significant_words(clean_movie_name(video.name))
        return " ".join(words)


class SubtitleService:
    """Analyse a local subtitle file and auto-fill its metadata."""

    def __init__(self, hasher: FileHasher, detector: LanguageDetector) -> None:
        self._hasher = hasher
        self._detector = detector

    def analyze(self, path: str | Path) -> SubtitleFile:
        file = _ensure_readable_file(Path(path), "subtitle")
        md5 = self._hasher.md5(file)
        language = self._detector.detect(file)
        content = _read_head(file, 200_000)
        name = file.name
        return SubtitleFile(
            path=file,
            name=name,
            size_bytes=file.stat().st_size,
            md5=md5,
            language=language,
            hearing_impaired=likely_hearing_impaired(content),
            machine_translated=has_machine_translation_markers(name)
            or has_machine_translation_markers(content),
            foreign_parts_only=has_foreign_only_markers(name) or file.stat().st_size < 5_000,
        )


def _read_head(path: Path, limit: int) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
        for encoding in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return ""
    except OSError:
        return ""


class UploadService:
    """Prepare and run a subtitle upload."""

    def __init__(
        self,
        uploader: OpenSubtitlesUploader,
        catalog: OpenSubtitlesCatalog,
    ) -> None:
        self._uploader = uploader
        self._catalog = catalog

    def upload(self, request: UploadRequest) -> UploadOutcome:
        language = request.effective_language
        if language is None:
            raise ValidationError(
                "Choose a subtitle language before uploading.", code="language_required"
            )
        movie = request.video.movie
        imdb_id = movie.imdb_id if movie else None
        outcome = self._uploader.upload(
            moviehash=request.video.os_hash,
            moviebytesize=request.video.size_bytes,
            language=language.code,
            subtitle_path=request.subtitle.path,
            imdb_id=imdb_id,
            movie_filename=request.video.name,
            release_name=request.release_name or None,
            fps=request.video.media.frame_rate,
            duration_ms=request.video.media.duration_ms,
            frames=request.video.media.frame_count,
            hearing_impaired=request.flags.hearing_impaired,
            machine_translation=request.flags.machine_translated,
            foreign_parts_only=request.flags.foreign_parts_only,
            high_definition=request.video.hd,
            translator=request.translator or None,
            comment=request.comment or None,
            subhash=request.subtitle.md5,
        )
        return outcome


def build_upload_request(
    video: VideoFile,
    subtitle: SubtitleFile,
    *,
    language: Language | None = None,
    movie_aka: str = "",
    release_name: str = "",
    high_definition: bool | None = None,
    translator: str = "",
    comment: str = "",
    hearing_impaired: bool | None = None,
    machine_translated: bool | None = None,
    foreign_parts_only: bool | None = None,
) -> UploadRequest:
    """Compose an upload request from analysed files and user edits."""
    return UploadRequest(
        video=video,
        subtitle=subtitle,
        language=language,
        movie_aka=movie_aka.strip() or None,
        release_name=release_name.strip() or None,
        high_definition=high_definition,
        translator=translator.strip() or None,
        comment=comment.strip() or None,
    ).with_flags(
        hearing_impaired=hearing_impaired,
        machine_translated=machine_translated,
        foreign_parts_only=foreign_parts_only,
    )
