"""
Auth dependencies.

There is no global auth middleware. Auth is a per-endpoint `Depends(...)`, which means
**the absence of a dependency is what makes a route public** — so any public route must
live in its own router and say so at the top of the file.

These are all sync (`def`), so FastAPI runs them in a worker threadpool. That is precisely
why tests must use `poolclass=StaticPool`; see .ai/instructions/06-testing-conventions.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.database.db import get_db
from flightlog.database.models import ApiKey, User
from flightlog.database.models import utcnow as db_utcnow
from flightlog.services.apikeys import parse_key_prefix, verify_key
from flightlog.services.auth import TokenError, decode_token

logger = logging.getLogger(__name__)

# auto_error=False so a missing header reaches our handler and produces the typed
# envelope rather than FastAPI's own {"detail": ...} shape.
_bearer = HTTPBearer(auto_error=False)


def _resolve_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        logger.info("Token rejected: %s", exc)
        return None
    return db.get(User, payload["sub"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_user(credentials, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Returns None instead of raising.

    Caveat, inherited deliberately: this does **not** check `is_active`. Never use it to
    guard anything that needs a live account — it exists for routes that merely personalise
    a public response.
    """
    return _resolve_user(credentials, db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user


def client_ip(request: Request) -> str:
    """Best-effort client address for audit logging. Behind Traefik, trust the header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@dataclass
class ApiPrincipal:
    """Resolved by `get_api_principal` from a valid `X-API-Key` header. `scopes` is the
    key's own granted set — never the owning user's full access."""

    user: User
    key: ApiKey
    scopes: set[str]


def get_api_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiPrincipal:
    """
    Resolves a valid, unrevoked, unexpired API key to its owning pilot and granted scopes.

    Every rejection reason (missing header, malformed key, unknown prefix, hash mismatch,
    revoked, expired, inactive owner) collapses to the same 401 — never a hint about which
    of those it was, matching this app's existing "never leak" discipline.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    prefix = parse_key_prefix(x_api_key)
    if prefix is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    row = db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix)).scalar_one_or_none()
    if row is None or not verify_key(x_api_key, row.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # revoked_at always wins over expires_at — there is no scenario where a revoked-but-
    # not-yet-expired key still works (spec.md's Edge Cases).
    if row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="API key revoked")
    if row.expires_at is not None and row.expires_at < db_utcnow():
        raise HTTPException(status_code=401, detail="API key expired")

    user = db.get(User, row.owner_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    row.last_used_at = db_utcnow()
    db.commit()

    return ApiPrincipal(user=user, key=row, scopes=set(row.scopes.split()))


def require_scope(scope: str):
    """Factory: resolves the principal, then checks the scope. 403, never 404 — this is a
    capability check, not an ownership check."""

    def _check(principal: ApiPrincipal = Depends(get_api_principal)) -> ApiPrincipal:
        if scope not in principal.scopes:
            raise HTTPException(status_code=403, detail=f"Missing required scope: {scope}")
        return principal

    return _check
