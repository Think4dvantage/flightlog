"""
The typed error envelope.

Every error leaves this service in exactly one shape:

    {"error": {"code": "...", "message": "...", "details": {}}}

This is **not** RFC 7807. Do not rename the keys to type/title/detail.
"""

from __future__ import annotations

from typing import Any

# The complete vocabulary. `ERROR` is the fallback for an unmapped 4xx — avoid relying on it.
CODE_VALIDATION_FAILED = "VALIDATION_FAILED"
CODE_AUTH_REQUIRED = "AUTH_REQUIRED"
CODE_PERMISSION_DENIED = "PERMISSION_DENIED"
CODE_ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
CODE_CONFLICT = "CONFLICT"
CODE_INTERNAL_ERROR = "INTERNAL_ERROR"
CODE_ERROR = "ERROR"

STATUS_TO_CODE: dict[int, str] = {
    400: CODE_VALIDATION_FAILED,
    401: CODE_AUTH_REQUIRED,
    403: CODE_PERMISSION_DENIED,
    404: CODE_ENTITY_NOT_FOUND,
    409: CODE_CONFLICT,
    422: CODE_VALIDATION_FAILED,
}


class AppException(Exception):
    """Raise when the error code matters. A plain HTTPException is fine otherwise."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def code_for_status(status_code: int) -> str:
    if status_code in STATUS_TO_CODE:
        return STATUS_TO_CODE[status_code]
    return CODE_INTERNAL_ERROR if status_code >= 500 else CODE_ERROR
