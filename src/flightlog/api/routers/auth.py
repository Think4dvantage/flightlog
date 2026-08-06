"""
Authentication.

    POST /api/auth/register              — gated by auth.allow_self_registration
    POST /api/auth/login                 — email + password -> token pair
    POST /api/auth/refresh               — rotate the token pair
    GET  /api/auth/me                    — current profile
    PUT  /api/auth/me                    — update display name / locale / timezone / units
    POST /api/auth/me/password           — change password (current password required)
    GET  /api/auth/registration-status   — unauthenticated; drives the Sign-up link
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import client_ip, get_current_user
from flightlog.api.errors import (
    CODE_AUTH_REQUIRED,
    CODE_CONFLICT,
    CODE_PERMISSION_DENIED,
    AppException,
)
from flightlog.config import get_config
from flightlog.database.db import get_db
from flightlog.database.models import User, utcnow
from flightlog.models.auth import (
    PasswordChange,
    RegistrationStatus,
    Token,
    TokenRefreshRequest,
    UserCreate,
    UserLogin,
    UserOut,
    UserUpdate,
)
from flightlog.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_tokens(user: User) -> Token:
    cfg = get_config().auth
    return Token(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        expires_in=cfg.access_token_expire_minutes * 60,
    )


def _find_by_email(db: Session, email: str) -> User | None:
    return db.execute(
        select(User).where(func.lower(User.email) == email.lower().strip())
    ).scalar_one_or_none()


# ---- registration ----------------------------------------------------------------


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status() -> RegistrationStatus:
    """Unauthenticated by design — the login page needs it before anyone has a token."""
    return RegistrationStatus(self_registration=get_config().auth.allow_self_registration)


@router.post("/register", response_model=Token, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)) -> Token:
    if not get_config().auth.allow_self_registration:
        logger.warning("Registration attempt while self-registration is disabled: %s", body.email)
        raise AppException(
            403,
            CODE_PERMISSION_DENIED,
            "Self-registration is disabled on this instance",
        )

    if _find_by_email(db, body.email) is not None:
        raise AppException(409, CODE_CONFLICT, "An account with that email already exists")

    user = User(
        email=body.email,
        display_name=body.display_name.strip(),
        hashed_password=hash_password(body.password),
        role="pilot",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Per-user defaults (flight categories) are seeded from here in v0.2, guarded by
    # users.seeded_at IS NULL.
    logger.info("User registered: %s (%s)", user.email, user.id)
    return _issue_tokens(user)


# ---- login / refresh -------------------------------------------------------------


@router.post("/login", response_model=Token)
def login(body: UserLogin, request: Request, db: Session = Depends(get_db)) -> Token:
    user = _find_by_email(db, body.email)

    # One message and one status for "no such account" and "wrong password" alike —
    # anything else turns login into an account-enumeration oracle.
    if user is None or not verify_password(body.password, user.hashed_password):
        logger.warning("Failed login for %s from %s", body.email, client_ip(request))
        raise AppException(401, CODE_AUTH_REQUIRED, "Invalid email or password")

    if not user.is_active:
        logger.warning("Login attempt on disabled account: %s", user.email)
        raise AppException(401, CODE_AUTH_REQUIRED, "Invalid email or password")

    user.last_login_at = utcnow()
    db.commit()

    logger.info("User logged in: %s from %s", user.email, client_ip(request))
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
def refresh(body: TokenRefreshRequest, db: Session = Depends(get_db)) -> Token:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except TokenError as exc:
        raise AppException(401, CODE_AUTH_REQUIRED, str(exc)) from exc

    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise AppException(401, CODE_AUTH_REQUIRED, "Account is no longer available")

    logger.info("Token refreshed for %s", user.id)
    return _issue_tokens(user)


# ---- profile ---------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    logger.info("Profile updated for %s: %s", current_user.id, sorted(changes))
    return current_user


@router.post("/me/password", status_code=204)
def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(body.current_password, current_user.hashed_password):
        logger.warning("Password change with wrong current password: %s", current_user.id)
        raise AppException(401, CODE_AUTH_REQUIRED, "Current password is incorrect")

    current_user.hashed_password = hash_password(body.password)
    db.commit()
    logger.info("Password changed for %s", current_user.id)
