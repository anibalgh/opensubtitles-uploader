"""Domain errors.

Every exception carries a stable machine-readable ``code`` plus a
human-readable message.  UI adapters translate ``code`` (or ``message``)
through their own i18n catalogues, so the core never depends on any
presentation framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainError(Exception):
    """Base class for all domain/application errors."""

    code: str = "domain_error"
    message: str = "Unexpected error"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


class ValidationError(DomainError):
    """Input provided by the user/UI is invalid or incomplete."""

    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(code=code, message=message)


class FileNotSupportedError(DomainError):
    def __init__(self, message: str, code: str = "file_not_supported") -> None:
        super().__init__(code=code, message=message)


class FileNotFoundError_(DomainError):
    def __init__(self, message: str, code: str = "file_not_found") -> None:
        super().__init__(code=code, message=message)


class AuthError(DomainError):
    """Login failed / session expired."""

    def __init__(self, message: str, code: str = "auth_error") -> None:
        super().__init__(code=code, message=message)


class ApiError(DomainError):
    """The OpenSubtitles service reported an error."""

    status_code: int | None = None
    details: Any = None

    def __init__(
        self,
        message: str,
        code: str = "api_error",
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(code=code, message=message)
        object.__setattr__(self, "status_code", status_code)
        object.__setattr__(self, "details", details)


class UnavailableError(ApiError):
    """The service is offline, under maintenance or rate-limited us."""

    def __init__(self, message: str, code: str = "service_unavailable") -> None:
        super().__init__(code=code, message=message)


class UploadFailedError(ApiError):
    """The upload request was rejected."""

    def __init__(self, message: str, code: str = "upload_failed") -> None:
        super().__init__(code=code, message=message)


class AlreadyExistsError(DomainError):
    """The subtitle (hash) is already present in the database."""

    def __init__(self, message: str, code: str = "already_exists") -> None:
        super().__init__(code=code, message=message)
