"""
Password hashing and JWT issuing/verification.

Two deliberate divergences from the blueprint defaults, both recorded in
.ai/instructions/01-project-overview.md:

- **PyJWT, not python-jose.** python-jose's last release is 3.5.0 (May 2025) and it carries
  a CVE history including algorithm confusion. PyJWT is maintained and makes `algorithms=`
  mandatory on decode — the exact parameter whose absence caused that CVE.
- **bcrypt directly, not passlib.** passlib is unmaintained and buys nothing here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from flightlog.config import get_config

logger = logging.getLogger(__name__)

TokenType = Literal["access", "refresh"]

# bcrypt truncates silently at 72 bytes. Reject longer inputs rather than letting two
# different passwords authenticate the same account.
BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password exceeds {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str | None) -> bool:
    """
    Constant-time-ish verification. A user with no password (OAuth-only, or not yet set)
    always fails rather than being treated as passwordless.
    """
    if not hashed:
        return False
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the DB — treat as a failed login, but make it visible.
        logger.error("Stored password hash is malformed")
        return False


def _create_token(subject: str, token_type: TokenType, expires: timedelta, **extra: Any) -> str:
    cfg = get_config().auth
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        **extra,
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    cfg = get_config().auth
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=cfg.access_token_expire_minutes),
        role=role,
    )


def create_refresh_token(user_id: str) -> str:
    cfg = get_config().auth
    return _create_token(user_id, "refresh", timedelta(days=cfg.refresh_token_expire_days))


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """
    Decode and validate a token, or raise TokenError.

    `algorithms=` is passed explicitly and non-negotiably: without it a decoder honours
    whatever the token's own header claims, including "none". That is the algorithm
    confusion class of bug.

    The `type` claim is checked here rather than at the call site so a refresh token can
    never be replayed as an access token.
    """
    cfg = get_config().auth
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token is invalid") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    if not payload.get("sub"):
        raise TokenError("Token has no subject")

    return payload
