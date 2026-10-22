"""Exception hierarchy shared by every layer of the application.

Each layer raises the most specific exception it can. Pages catch these and
show a friendly message instead of a stack trace:

    AppError
    ├── DatabaseError
    │   ├── DatabaseConnectionError   - cannot reach the database
    │   └── RecordInUseError          - delete blocked by a foreign key
    ├── ValidationError               - user input failed validation
    └── APIError
        ├── APIAuthError              - 401/403: bad key or not subscribed
        ├── APINotFoundError          - 404: unknown id or path
        ├── APIRateLimitError         - 429: quota or rate limit reached
        └── APIResponseError          - 5xx, timeouts, malformed JSON
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all expected, user-explainable application errors."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail  # technical detail for logs, not for users


# ----------------------------- Database ------------------------------------
class DatabaseError(AppError):
    """A database operation failed."""


class DatabaseConnectionError(DatabaseError):
    """The database could not be reached (wrong URL, server down, no internet)."""


class RecordInUseError(DatabaseError):
    """A record cannot be deleted because other records reference it."""


# ----------------------------- Validation ----------------------------------
class ValidationError(AppError):
    """User input failed validation.

    Attributes:
        errors: one human-readable message per invalid field.
    """

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


# ----------------------------- API -----------------------------------------
class APIError(AppError):
    """Base class for Cricbuzz API failures."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.status_code = status_code


class APIAuthError(APIError):
    """401/403 - invalid API key, or not subscribed to the API on RapidAPI."""


class APINotFoundError(APIError):
    """404 - the requested match, player or endpoint does not exist."""


class APIRateLimitError(APIError):
    """429 - request quota or per-second rate limit exceeded."""


class APIResponseError(APIError):
    """Server error, timeout, or a response body that could not be parsed."""
