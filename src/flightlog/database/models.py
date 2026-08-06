"""
SQLAlchemy ORM models for Flightlog.

`database/models.py` is the single source of truth for the schema. New tables are created
by `Base.metadata.create_all()`; new *columns* need an idempotent guard in
`db._run_column_migrations()`. There is no Alembic, no .sql files and no _migrations table.

Tables
------
users   — pilot accounts (local password; OAuth-ready via nullable hashed_password)

Tables arriving in later milestones are listed in .ai/context/architecture.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class UtcDateTime(TypeDecorator):
    """
    A timezone-aware datetime that survives SQLite.

    SQLite has no native timestamp type and stores no offset, so plain
    `DateTime(timezone=True)` silently returns a **naive** datetime on read. The value is
    UTC, but nothing in the API response says so — a client sees
    `2026-08-06T13:12:59.275499` and cannot tell whether that is UTC or local.

    That ambiguity is cheap to remove now and expensive later: the VidFactory contract
    hands out `takeoff_at_utc`, and IGC tracks are anchored on absolute UTC. So: coerce to
    UTC on the way in, re-attach UTC on the way out, in one place.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive value reaching the DB is a bug at the call site, but storing it as
            # UTC is strictly better than storing an unmarked local time.
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """
    A pilot account.

    Accounts are keyed on `email` with a separate `display_name`. There is deliberately
    no `username` field — one fewer identifier to keep unique, and email is what a
    password reset needs anyway.
    """

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)

    # Nullable so an OAuth-only account can exist later without a password row.
    hashed_password = Column(String, nullable=True)

    role = Column(String, nullable=False, default="pilot")  # pilot | admin
    is_active = Column(Boolean, nullable=False, default=True)

    # Presentation preferences
    locale = Column(String, nullable=False, default="en")
    timezone = Column(String, nullable=False, default="Europe/Zurich")  # IANA
    units = Column(String, nullable=False, default="metric")  # metric | imperial

    # Set once the per-user defaults (flight categories) have been seeded.
    # Guards re-seeding without needing a separate flag table.
    seeded_at = Column(UtcDateTime, nullable=True)

    last_login_at = Column(UtcDateTime, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email} role={self.role}>"
