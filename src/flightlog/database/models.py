"""
SQLAlchemy ORM models for Flightlog.

`database/models.py` is the single source of truth for the schema. New tables are created
by `Base.metadata.create_all()`; new *columns* need an idempotent guard in
`db._run_column_migrations()`. There is no Alembic, no .sql files and no _migrations table.

Tables
------
users              — pilot accounts (local password; OAuth-ready via nullable hashed_password)
regions            — shared reference data, not owner-scoped
sites              — launch/landing sites; owner_id nullable, reserved for a v0.8 shared catalogue
user_site_prefs    — per-pilot alias/elevation/favourite overlay on a site
gliders, harnesses — owner-scoped gear
flight_categories  — owner-scoped, drives statistics via is_hike_fly / is_training
buddies            — owner-scoped contact, optional two-sided link to another pilot account
flights            — the core record; altitude-derived figures are computed on read, never stored
flight_buddies     — flight <-> buddy join table

Tables arriving in later milestones are listed in .ai/context/architecture.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


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

    # cascade="all, delete-orphan" is what actually deletes a pilot's owned rows —
    # PRAGMA foreign_keys is never turned on, so ondelete="CASCADE" on the Column below is
    # documentation only. No route deletes a user yet (v0.2 has no account-deletion
    # endpoint), but wiring this now avoids silently orphaned rows the day one is added.
    sites = relationship("Site", back_populates="owner", cascade="all, delete-orphan")
    gliders = relationship("Glider", back_populates="owner", cascade="all, delete-orphan")
    harnesses = relationship("Harness", back_populates="owner", cascade="all, delete-orphan")
    flight_categories = relationship(
        "FlightCategory", back_populates="owner", cascade="all, delete-orphan"
    )
    buddies = relationship(
        "Buddy",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="[Buddy.owner_id]",
    )
    flights = relationship("Flight", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email} role={self.role}>"


class Region(Base):
    """
    Shared reference data grouping sites by area. Not owner-scoped — same rows for every pilot.

    Seeded once in db.py from a list hand-transcribed from the legacy workbook's "Flight Area"
    SUM formulas — see specs/001-core-data-import/research.md for how that mapping was derived.
    """

    __tablename__ = "regions"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, unique=True, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class Site(Base):
    """
    A launch and/or landing site. One row can serve both roles — the legacy workbook kept two
    separate lists, but some real places (e.g. Schiltgrat) appear in both at the same elevation.
    """

    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint("is_launch = 1 OR is_landing = 1", name="ck_sites_launch_or_landing"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    # Nullable — reserved for a future shared catalogue (v0.8). No row uses NULL yet; every
    # v0.2 site is owner-set. See architecture.md.
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    is_launch = Column(Boolean, nullable=False, default=False)
    is_landing = Column(Boolean, nullable=False, default=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    elevation_m = Column(Integer, nullable=True)
    # Not written before IGC backfill exists (v0.4) — declared now because this table is
    # being created fresh; adding it later would need a _run_column_migrations() guard.
    elevation_igc_m = Column(Integer, nullable=True)
    region_id = Column(String, ForeignKey("regions.id"), nullable=True)
    coord_source = Column(String, nullable=True)  # "manual" in v0.2; "igc_median" arrives v0.4
    coord_accuracy_m = Column(Float, nullable=True)  # unpopulated until v0.4, same reasoning
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="sites")


class UserSitePref(Base):
    """A pilot's personal overlay on a site they don't necessarily own — alias, elevation override,
    favourite/hidden flags."""

    __tablename__ = "user_site_prefs"
    __table_args__ = (PrimaryKeyConstraint("user_id", "site_id"),)

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(String, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=True)
    elevation_m = Column(Integer, nullable=True)
    is_favourite = Column(Boolean, nullable=False, default=False)
    is_hidden = Column(Boolean, nullable=False, default=False)


class Glider(Base):
    __tablename__ = "gliders"

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    size = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    en_class = Column(String, nullable=True)  # not in the legacy data — left null on import
    is_own = Column(Boolean, nullable=False, default=True)
    retired_at = Column(UtcDateTime, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="gliders")


class Harness(Base):
    __tablename__ = "harnesses"

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    size = Column(String, nullable=True)
    harness_type = Column(String, nullable=True)  # not in the legacy data — left null on import
    reserve_next_repack = Column(UtcDateTime, nullable=True)
    retired_at = Column(UtcDateTime, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="harnesses")


class FlightCategory(Base):
    """Owner-scoped flight category. Archived, never hard-deleted, once a flight references it."""

    __tablename__ = "flight_categories"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_flight_categories_owner_slug"),)

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    is_hike_fly = Column(Boolean, nullable=False, default=False)
    is_training = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    archived_at = Column(UtcDateTime, nullable=True)

    owner = relationship("User", back_populates="flight_categories")


class Buddy(Base):
    """
    A flying buddy contact. Always belongs to its creator — linking to another pilot's account
    is enrichment, never ownership. Deleting a buddy never touches the linked account.
    """

    __tablename__ = "buddies"

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name = Column(String, nullable=False)
    linked_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    link_state = Column(String, nullable=False, default="none")  # none|pending|confirmed|declined
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="buddies", foreign_keys=[owner_id])


class Flight(Base):
    """
    The core record. Altitude-derived figures (alt_gain_m, site_drop_m, total_descent_m) are
    **not columns** — they are computed on read from max_alt_m and the effective launch/landing
    elevations (COALESCE of a flight override, a user_site_prefs override, then sites.elevation_m).
    See architecture.md for why: a site elevation correction must retroactively fix every flight.
    """

    __tablename__ = "flights"
    __table_args__ = (
        # Unique per owner, not globally — a global constraint would break the day-one
        # tenancy rule the moment a second pilot's import produces the same "xlsx:5".
        UniqueConstraint("owner_id", "import_key", name="uq_flights_owner_import_key"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flight_date = Column(Date, nullable=False)
    # Null until IGC attach (v0.4) backfills them from the track.
    takeoff_time = Column(UtcDateTime, nullable=True)
    landing_time = Column(UtcDateTime, nullable=True)
    # A row the importer can't resolve is skipped and reported, never inserted with a
    # placeholder — so this is NOT NULL in practice, never defensively nullable.
    launch_site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    landing_site_id = Column(String, ForeignKey("sites.id"), nullable=True)
    category_id = Column(String, ForeignKey("flight_categories.id"), nullable=False)
    glider_id = Column(String, ForeignKey("gliders.id"), nullable=True)
    harness_id = Column(String, ForeignKey("harnesses.id"), nullable=True)
    duration_min = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    max_alt_m = Column(Integer, nullable=True)
    launch_elev_override_m = Column(Integer, nullable=True)
    landing_elev_override_m = Column(Integer, nullable=True)
    launch_technique = Column(String, nullable=True)  # forward|reverse
    notes = Column(Text, nullable=True)
    import_key = Column(String, nullable=True)  # "xlsx:<row>"; NULL for API-created flights
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="flights", foreign_keys=[owner_id])


class FlightBuddy(Base):
    __tablename__ = "flight_buddies"
    __table_args__ = (PrimaryKeyConstraint("flight_id", "buddy_id"),)

    flight_id = Column(String, ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    buddy_id = Column(String, ForeignKey("buddies.id", ondelete="CASCADE"), nullable=False)
