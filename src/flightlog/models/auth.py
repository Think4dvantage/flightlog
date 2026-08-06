"""Pydantic schemas for authentication and user profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# Long enough to matter, short enough not to annoy. bcrypt's own ceiling is 72 bytes.
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 72


class _PasswordMixin(BaseModel):
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("password")
    @classmethod
    def _not_all_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password cannot be blank")
        return v


class UserCreate(_PasswordMixin):
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class UserUpdate(BaseModel):
    """PATCH semantics — every field optional, applied with exclude_unset=True."""

    display_name: str | None = Field(None, min_length=1, max_length=80)
    locale: str | None = None
    timezone: str | None = None
    units: Literal["metric", "imperial"] | None = None


class PasswordChange(_PasswordMixin):
    """`password` is the new one; the current password is required to authorise."""

    current_password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    locale: str
    timezone: str
    units: str
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds until the access token expires


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class RegistrationStatus(BaseModel):
    """Lets the login page decide whether to show a Sign-up link."""

    self_registration: bool
