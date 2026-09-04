"""OpenSubtitles adapter.

Hybrid client that mirrors the actual state of the OpenSubtitles APIs
(verified live 2026-09-03):

- **REST** (``api.opensubtitles.com/api/v1``, needs an ``Api-Key``):
  catalog — feature search, hash-based identification, languages.
- **Legacy XML-RPC** (``api.opensubtitles.org/xml-rpc``, needs a user
  login token): the actual upload workflow — ``TryUploadSubtitles``
  (duplicate check) and ``UploadSubtitles``.  The public REST API has no
  upload endpoint.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import threading
from pathlib import Path
from typing import Any

import httpx

from opensubtitles_uploader import __version__
from opensubtitles_uploader.adapters.media.dataset import bundled_language_index
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.adapters.osapi.xmlrpc import XmlRpcClient
from opensubtitles_uploader.config import (
    HTTP_TIMEOUT,
    OS_BASE_URL,
    environment_metadata_credentials,
)
from opensubtitles_uploader.domain.errors import (
    ApiError,
    AuthError,
    UnavailableError,
    UploadFailedError,
)
from opensubtitles_uploader.domain.model import (
    ExistingMatch,
    Language,
    MediaKind,
    MovieRef,
    Session,
    UploadOutcome,
    UserInfo,
)

USER_AGENT = f"OpenSubtitles-Uploader v{__version__}"

_XMLRPC_ENDPOINT = "https://api.opensubtitles.org/xml-rpc"

# REST error -> our error code
_STATUS_CODES: dict[int, str] = {
    401: "auth_error",
    403: "forbidden",
    404: "not_found",
    422: "invalid_input",
    429: "rate_limited",
    503: "service_unavailable",
}


class _LanguageCatalogue:
    """Subtitle-language list resolved from multiple sources."""

    def __init__(
        self, xmlrpc: XmlRpcClient, http: httpx.Client, base_url: str, headers: dict[str, str]
    ) -> None:
        self._xmlrpc = xmlrpc
        self._http = http
        self._base_url = base_url
        self._headers = headers
        self._cache: list[Language] | None = None

    def languages(self) -> list[Language]:
        if self._cache is None:
            self._cache = self._load()
        return self._cache

    def _load(self) -> list[Language]:
        bundled = bundled_language_index()
        # 1) XML-RPC GetSubLanguages: {SubLanguageID: 'eng', ISO639: 'en', LanguageName}
        rows = self._xmlrpc.get_sub_languages()
        if rows:
            languages: list[Language] = []
            for row in rows:
                code = str(row.get("SubLanguageID") or "").strip()
                iso = str(row.get("ISO639") or "").strip()
                name = str(row.get("LanguageName") or "").strip()
                if not code:
                    continue
                existing = bundled.get(code.lower()) or bundled.get(iso.lower())
                languages.append(
                    Language(
                        code=code,
                        iso639_1=iso,
                        name=name or (existing.name if existing else code),
                        native=(
                            existing.native
                            if existing and existing.native != existing.name
                            else name
                        )
                        or name,
                    )
                )
            if languages:
                return sorted(languages, key=lambda lang: lang.name.lower())

        # 2) REST /infos/languages (2-letter codes) as a fallback.
        try:
            response = self._http.get(
                f"{self._base_url}/infos/languages", headers=self._headers, timeout=HTTP_TIMEOUT
            )
            if response.status_code == 200:
                payload = response.json()
                languages = []
                for entry in payload.get("data", []):
                    code2 = str(entry.get("language_code") or "").strip()
                    name = str(entry.get("language_name") or "").strip()
                    existing = bundled.get(code2.lower())
                    if existing is not None:
                        languages.append(existing)
                    elif name and code2:
                        languages.append(
                            Language(code=code2, iso639_1=code2, name=name, native=name)
                        )
                if languages:
                    return sorted(set(languages), key=lambda lang: lang.name.lower())
        except (httpx.HTTPError, ValueError):
            pass

        # 3) Bundled dataset (always works offline).
        return sorted(bundled.values(), key=lambda lang: lang.name.lower())


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_imdb(value: Any) -> str:
    """``1375666``/``"1375666"`` -> ``"tt1375666"`` (zero-padded to 7 digits)."""
    try:
        return f"tt{int(value):07d}"
    except (TypeError, ValueError):
        return str(value).lower()


def _kind_from(feature_type: str | None) -> MediaKind | None:
    name = (feature_type or "").lower()
    if "episode" in name:
        return MediaKind.EPISODE
    if "tv" in name or "show" in name:
        return MediaKind.SHOW
    if "movie" in name:
        return MediaKind.MOVIE
    return None


def _parse_feature(
    attributes: dict[str, Any], fallback_title: str | None = None
) -> MovieRef | None:
    imdb_raw = attributes.get("imdb_id")
    if imdb_raw is None:
        return None
    kind = _kind_from(attributes.get("feature_type"))
    if kind == MediaKind.EPISODE:
        title = str(
            attributes.get("parent_title") or attributes.get("title") or fallback_title or ""
        )
        season = _as_int(attributes.get("season_number"))
        episode = _as_int(attributes.get("episode_number"))
    else:
        title = str(attributes.get("title") or fallback_title or "")
        season = None
        episode = None
    year = _as_int(attributes.get("year"))
    backdrop = attributes.get("img_url") or attributes.get("backdrop_path")
    return MovieRef(
        imdb_id=_normalize_imdb(imdb_raw),
        title=title.strip(),
        year=year,
        kind=kind,
        season=season,
        episode=episode,
        backdrop_url=str(backdrop) if backdrop else None,
    )


class OpenSubtitlesClient:
    """Implements every OpenSubtitles port with REST + XML-RPC."""

    def __init__(
        self,
        *,
        api_key: ApiKeySource,
        rest_base_url: str = OS_BASE_URL,
        user_agent: str = USER_AGENT,
        timeout: float = HTTP_TIMEOUT,
        xmlrpc_endpoint: str = _XMLRPC_ENDPOINT,
    ) -> None:
        self._api_key = api_key
        self._user_agent = user_agent
        self._rest_base = rest_base_url.rstrip("/")

        # --- upload session (GUI login -> legacy XML-RPC endpoint) -------
        self._xml_token: str | None = None
        self._upload_user: UserInfo | None = None

        # --- metadata/catalogue session (REST, credentials from .env) ----
        self._rest_token: str | None = None
        self._rest_user: UserInfo | None = None
        self._metadata_attempted = False
        self._metadata_error: str | None = None
        self._metadata_lock = threading.Lock()

        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )
        self._xmlrpc = XmlRpcClient(xmlrpc_endpoint, user_agent, timeout)
        self._catalogue = _LanguageCatalogue(
            self._xmlrpc, self._http, self._rest_base, self._headers()
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": self._user_agent}
        key = self._api_key.resolve()
        if key:
            headers["Api-Key"] = key
        if self._rest_token:
            headers["Authorization"] = f"Bearer {self._rest_token}"
        return headers

    def _rest(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = self._api_key.resolve()
        public = method == "GET" and path == "/infos/languages"
        if not key and not public:
            raise ApiError(
                "Configure an OpenSubtitles API key (Settings) to use this feature.",
                code="api_key_required",
            )
        try:
            response = self._http.request(
                method,
                f"{self._rest_base}{path}",
                params=params,
                json=json_body,
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise ApiError(str(exc), code="network_error") from exc

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return {}
            return data if isinstance(data, dict) else {}

        message = self._describe_error(response)
        code = _STATUS_CODES.get(response.status_code, "api_error")
        if response.status_code == 429:
            raise UnavailableError(message or "Rate limited by OpenSubtitles.", code="rate_limited")
        if response.status_code in (503, 502, 504):
            raise UnavailableError(message or "OpenSubtitles is temporarily unavailable.")
        raise ApiError(message or f"OpenSubtitles error {response.status_code}", code=code)

    @staticmethod
    def _describe_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return ""
        for key in ("message", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return " ".join(str(e) for e in errors)
        return ""

    def _require_xml_token(self) -> str:
        if not self._xml_token:
            raise AuthError(
                "Log in with an opensubtitles.org (legacy) account to upload.",
                code="upload_account_required",
            )
        return self._xml_token

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self, username: str, password: str) -> Session:
        """Upload login (GUI) — the *legacy XML-RPC* account.

        The credentials typed in the GUI belong to the opensubtitles.org
        upload world.  Catalogue/metadata lookups are a separate concern
        driven by :meth:`ensure_metadata_session` (.env credentials), so
        this method does **not** touch REST /login.
        """
        self._xml_token = self._xmlrpc.login(username, password)  # raises AuthError
        user = UserInfo(user_id=0, username=username, level="user", upload_capable=True)
        self._upload_user = user
        return Session(token=self._xml_token or "", user=user, base_url=self._rest_base)

    def ensure_metadata_session(self) -> UserInfo | None:
        """Log the REST/catalogue account (credentials from ``.env``) in once.

        Idempotent and thread-safe.  Returns the metadata profile, or
        ``None`` when no credentials/API key are configured or the login
        fails (the catalogue keeps working with the plain ``Api-Key``).
        When it fails, :attr:`metadata_error` holds the reason.
        """
        creds = environment_metadata_credentials()
        if not creds or not self._api_key.resolve():
            self._metadata_attempted = True
            self._metadata_error = (
                "OPENSUBTITLES_USERNAME/PASSWORD or the API key are not configured."
            )
            return self._rest_user
        with self._metadata_lock:
            if self._metadata_attempted:
                return self._rest_user
            self._metadata_attempted = True
            self._metadata_error = None
            username, password = creds
            try:
                payload = self._rest(
                    "POST", "/login", json_body={"username": username, "password": password}
                )
            except ApiError as exc:
                self._metadata_error = exc.message or str(exc)
                return None
            token = payload.get("token")
            if token:
                self._rest_token = str(token)
                base = payload.get("base_url")
                if isinstance(base, str) and base.startswith("http"):
                    self._rest_base = base
            raw_user = payload.get("user") or {}
            self._rest_user = UserInfo(
                user_id=_as_int(raw_user.get("user_id")) or 0,
                username=str(raw_user.get("username") or username),
                level=str(raw_user.get("level") or "user"),
                vip=bool(raw_user.get("vip")),
                upload_capable=False,  # metadata account never uploads
            )
            return self._rest_user

    def metadata_user(self) -> UserInfo | None:
        """The current metadata/catalogue profile (without logging in)."""
        return self._rest_user

    @property
    def metadata_error(self) -> str | None:
        """Reason of the last failed metadata login (``None`` when ok)."""
        return self._metadata_error

    def whoami(self) -> UserInfo:
        """Prefer the metadata (.env) profile, then the upload (GUI) one."""
        if self._rest_user is None:
            self.ensure_metadata_session()
        if self._rest_user:
            return self._rest_user
        if self._upload_user:
            return self._upload_user
        raise AuthError("Not logged in.", code="auth_required")

    def logout(self) -> None:
        """Revoke the upload (GUI) session and the REST bearer.

        The metadata account comes from configuration (.env), so the next
        catalogue call simply re-authenticates it.
        """
        if self._xml_token:
            self._xmlrpc.logout(self._xml_token)
        if self._rest_token:
            with contextlib.suppress(ApiError):
                self._rest("DELETE", "/logout")
        self._xml_token = None
        self._upload_user = None
        self._rest_token = None
        self._rest_user = None
        self._metadata_attempted = False
        self._metadata_error = None

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    def identify(self, moviehash: str, moviebytesize: int) -> MovieRef | None:
        """Map a video hash to a movie via subtitle search (REST)."""
        self.ensure_metadata_session()
        payload = self._rest(
            "GET",
            "/subtitles",
            params={
                "moviehash": moviehash,
                "moviebytesize": str(moviebytesize),
                "moviehash_match": "only",
            },
        )
        for item in payload.get("data", []):
            attributes = item.get("attributes") or {}
            if attributes.get("moviehash_match") is not True and not attributes.get(
                "feature_details"
            ):
                continue
            details = attributes.get("feature_details") or {}
            movie = _parse_feature(details)
            if movie:
                return movie
        return None

    def guess_movie(self, filename: str) -> MovieRef | None:
        from opensubtitles_uploader.domain.naming import clean_movie_name

        title = clean_movie_name(filename)
        if not title:
            return None
        results = self.search_features(title)
        return results[0] if results else None

    def search_features(self, query: str) -> list[MovieRef]:
        self.ensure_metadata_session()
        payload = self._rest("GET", "/features", params={"query": query, "full_search": "1"})
        results: list[MovieRef] = []
        for item in payload.get("data", []):
            attributes = item.get("attributes") or {}
            movie = _parse_feature(attributes)
            if movie:
                results.append(movie)
        return results

    def feature_details(self, imdb_id: str) -> MovieRef | None:
        self.ensure_metadata_session()
        digits = imdb_id.lower().lstrip("t")
        if not digits.isdigit():
            return None
        payload = self._rest("GET", "/features", params={"imdb_id": digits})
        data = payload.get("data", [])
        # Prefer a plain movie/show result when the id is a series.
        parsed = [
            movie
            for movie in (_parse_feature(item.get("attributes") or {}) for item in data)
            if movie
        ]
        if not parsed:
            return None
        for movie in parsed:
            if movie.kind in (MediaKind.MOVIE, MediaKind.SHOW):
                return movie
        return parsed[0]

    def languages(self) -> list[Language]:
        return self._catalogue.languages()

    # ------------------------------------------------------------------
    # Upload (XML-RPC)
    # ------------------------------------------------------------------
    @staticmethod
    def _osu_gzip(content: bytes) -> str:
        """Base64 of the zlib (RFC 1950) compressed subtitle.

        This mirrors the encoding used by the original
        ``opensubtitles-api`` (``zlib.deflate`` in Node.js) which the legacy
        XML-RPC endpoint expects for ``subcontent``.  *Not* gzip: a gzip
        payload makes the server report "SubHashes ... not same" and
        "invalid format".
        """
        import zlib

        compressed = zlib.compress(content)
        return base64.b64encode(compressed).decode("ascii")

    @staticmethod
    def _cd1(
        *,
        moviehash: str,
        moviebytesize: int,
        subtitle_path: Path,
        movie_filename: str | None,
        subhash: str | None,
        duration_ms: int | None,
        frames: int | None,
        fps: float | None,
        with_content: bool,
    ) -> dict[str, Any]:
        cd: dict[str, Any] = {
            "subhash": subhash or _content_md5(subtitle_path),
            "subfilename": subtitle_path.name,
            "moviehash": moviehash,
            "moviebytesize": moviebytesize,
            "moviefilename": movie_filename or "",
        }
        if duration_ms:
            cd["movietimems"] = duration_ms
        if frames:
            cd["movieframes"] = frames
        if fps:
            cd["moviefps"] = round(fps, 3)
        if with_content:
            cd["subcontent"] = OpenSubtitlesClient._osu_gzip(_read_bytes(subtitle_path))
        return cd

    def check_existing(
        self, moviehash: str, moviebytesize: int, subhash: str | None = None
    ) -> list[ExistingMatch]:
        token = self._require_xml_token()
        cd = {"moviehash": moviehash, "moviebytesize": moviebytesize}
        if subhash:
            cd["subhash"] = subhash
        result = self._xmlrpc.try_upload_subtitles(token, cd)
        if str(result.get("status", "")).startswith("200") and result.get("alreadyindb") == 1:
            return self._parse_existing(result)
        return []

    @staticmethod
    def _parse_existing(result: dict[str, Any]) -> list[ExistingMatch]:
        matches: list[ExistingMatch] = []
        data = result.get("data") or []
        if isinstance(data, dict):
            data = [data]
        for entry in data if isinstance(data, list) else []:
            matched_by: list[str] = []
            if entry.get("HashWasAlreadyInDb") == 1:
                matched_by.append("moviehash")
            if entry.get("MoviefilenameWasAlreadyInDb") == 1:
                matched_by.append("filename")
            if entry.get("SubHashWasAlreadyInDb") == 1:
                matched_by.append("subhash")
            matches.append(
                ExistingMatch(
                    subtitle_id=_as_int(entry.get("IDSubtitle")) or 0,
                    url=(
                        f"https://www.opensubtitles.org/subtitles/{entry.get('IDSubtitle')}"
                        if entry.get("IDSubtitle")
                        else None
                    ),
                    lang_code=str(entry.get("SubLanguageID") or ""),
                    movie_name=str(entry.get("MovieName") or ""),
                    matched_by=tuple(matched_by),
                )
            )
        return matches

    def upload(
        self,
        *,
        moviehash: str,
        moviebytesize: int,
        language: str,
        subtitle_path: Path,
        imdb_id: str | None = None,
        movie_filename: str | None = None,
        release_name: str | None = None,
        fps: float | None = None,
        duration_ms: int | None = None,
        frames: int | None = None,
        hearing_impaired: bool | None = None,
        machine_translation: bool | None = None,
        foreign_parts_only: bool | None = None,
        high_definition: bool | None = None,
        translator: str | None = None,
        comment: str | None = None,
        subhash: str | None = None,
    ) -> UploadOutcome:
        token = self._require_xml_token()

        # 1) Preliminary TryUploadSubtitles: the server is authoritative —
        #    it tells us whether the subtitle is already in the database and
        #    returns the movie ID matching this exact video hash (important
        #    for TV episodes, where a generic show id would be rejected).
        probe_cd = self._cd1(
            moviehash=moviehash,
            moviebytesize=moviebytesize,
            subtitle_path=subtitle_path,
            movie_filename=movie_filename,
            subhash=subhash,
            duration_ms=duration_ms,
            frames=frames,
            fps=fps,
            with_content=False,
        )
        try_result = self._xmlrpc.try_upload_subtitles(token, probe_cd)
        try_status = str(try_result.get("status", "") or "")
        if not try_status.startswith("200"):
            raise UploadFailedError(
                try_status or "OpenSubtitles could not check the subtitle.",
                code="upload_failed",
            )
        if try_result.get("alreadyindb") == 1:
            return UploadOutcome(state="already_exists", existing=self._parse_existing(try_result))
        data = try_result.get("data") or []
        if isinstance(data, dict):
            data = [data]
        authoritative_imdb = None
        if data and data[0].get("IDMovieImdb"):
            authoritative_imdb = str(data[0]["IDMovieImdb"])
        movie_imdb = authoritative_imdb or imdb_id

        # 2) Real upload.
        baseinfo: dict[str, Any] = {
            "sublanguageid": language,
        }
        if movie_imdb:
            baseinfo["idmovieimdb"] = str(movie_imdb).lower().lstrip("t")
        if release_name:
            baseinfo["moviereleasename"] = release_name
        if comment:
            baseinfo["subauthorcomment"] = comment
        if translator:
            baseinfo["subtranslator"] = translator
        for key, flag in (
            ("hearingimpaired", hearing_impaired),
            ("highdefinition", high_definition),
            ("foreignpartsonly", foreign_parts_only),
            ("automatictranslation", machine_translation),
        ):
            if flag is not None:
                baseinfo[key] = "1" if flag else "0"

        cd1 = self._cd1(
            moviehash=moviehash,
            moviebytesize=moviebytesize,
            subtitle_path=subtitle_path,
            movie_filename=movie_filename,
            subhash=subhash,
            duration_ms=duration_ms,
            frames=frames,
            fps=fps,
            with_content=True,
        )
        result = self._xmlrpc.upload_subtitles(token, baseinfo, cd1)
        return self._interpret_upload(result)

    @staticmethod
    def _interpret_upload(result: dict[str, Any]) -> UploadOutcome:
        status = str(result.get("status", ""))
        data = result.get("data")
        if status.startswith("200"):
            if isinstance(data, str) and data:
                return UploadOutcome(state="created", url=data, message_code="upload_ok")
            if isinstance(data, dict) and data.get("url"):
                return UploadOutcome(
                    state="created", url=str(data["url"]), message_code="upload_ok"
                )
            return UploadOutcome(state="created", message_code="upload_ok")

        lowered = (status + " " + str(data)).lower()
        if "already" in lowered or "exists" in lowered:
            return UploadOutcome(
                state="already_exists", url=str(data) if isinstance(data, str) else None
            )
        if isinstance(data, str) and data:
            raise UploadFailedError(data, code="upload_failed")
        raise UploadFailedError(status or "Unknown upload error", code="upload_failed")


def _content_md5(path: Path) -> str:
    # Content fingerprint for OpenSubtitles (not a security hash).
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()
