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

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from flightlog.database.db import get_db
from flightlog.database.models import User
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
