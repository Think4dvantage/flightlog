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
igc_tracks         — one analyzed GPS track per flight; file on disk, aggregates here
igc_segments       — thermals/glides/markers within a track, takeoff-relative offsets
site_observations  — a track's takeoff/landing fix, feeding sites' automatic coordinate backfill
igc_pending_uploads — a bulk-uploaded file that didn't auto-attach to a flight
hikes              — Fitnessprogramm sheet; optionally linked to a Hike&Fly flight
groundhandling_sessions — Groundhandling sheet; standalone, never linked to a flight
tandem_flights     — Tandemflüge sheet; the pilot as passenger, deliberately not in flights
goals              — Ziele sheet; the one imported type that stays editable afterward
api_keys           — pilot-minted, scoped machine credentials (v0.8); plaintext never stored
flight_links       — external resources (e.g. VidFactory videos) pushed back onto a flight

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
    igc_tracks = relationship("IgcTrack", back_populates="owner", cascade="all, delete-orphan")
    igc_pending_uploads = relationship(
        "IgcPendingUpload", back_populates="owner", cascade="all, delete-orphan"
    )
    hikes = relationship("Hike", back_populates="owner", cascade="all, delete-orphan")
    groundhandling_sessions = relationship(
        "GroundhandlingSession", back_populates="owner", cascade="all, delete-orphan"
    )
    tandem_flights = relationship(
        "TandemFlight", back_populates="owner", cascade="all, delete-orphan"
    )
    goals = relationship("Goal", back_populates="owner", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="owner", cascade="all, delete-orphan")

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
    igc_track = relationship(
        "IgcTrack", back_populates="flight", uselist=False, cascade="all, delete-orphan"
    )
    links = relationship("FlightLink", cascade="all, delete-orphan")


class FlightBuddy(Base):
    __tablename__ = "flight_buddies"
    __table_args__ = (PrimaryKeyConstraint("flight_id", "buddy_id"),)

    flight_id = Column(String, ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    buddy_id = Column(String, ForeignKey("buddies.id", ondelete="CASCADE"), nullable=False)


class IgcTrack(Base):
    """
    A flight's analyzed GPS track — at most one per flight; a re-upload replaces this row
    wholesale rather than accumulating a second one (specs/003-igc-ingest-analysis spec.md
    FR-004). The uploaded file itself lives on disk, content-addressed
    (core/igc_storage.py); raw fixes are never stored here — track_simplified_json is a
    derived, regenerable reduced-resolution point series, not the source of truth.
    """

    __tablename__ = "igc_tracks"
    __table_args__ = (
        UniqueConstraint("flight_id", name="uq_igc_tracks_flight_id"),
        # Per-owner, not global — same reasoning as flights.import_key.
        UniqueConstraint("owner_id", "sha256", name="uq_igc_tracks_owner_sha256"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flight_id = Column(String, ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    duration_s = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    max_alt_igc_m = Column(Integer, nullable=True)
    alt_gain_igc_m = Column(Integer, nullable=True)
    thermal_count = Column(Integer, nullable=True)
    best_climb_ms = Column(Float, nullable=True)
    peak_climb_ms = Column(Float, nullable=True)
    glide_ratio = Column(Float, nullable=True)
    # libigc's own AltitudeSource value ("PRESS" | "GNSS") — read from flight.alt_source,
    # never recomputed from the raw fixes; see research.md for why.
    alt_source = Column(String, nullable=True)
    track_simplified_json = Column(Text, nullable=True)
    analyzer_version = Column(String, nullable=False)
    analyzed_at = Column(UtcDateTime, nullable=False)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="igc_tracks")
    flight = relationship("Flight", back_populates="igc_track")
    segments = relationship(
        "IgcSegment",
        cascade="all, delete-orphan",
        order_by="IgcSegment.start_offset_s",
    )
    observations = relationship("SiteObservation", cascade="all, delete-orphan")


class IgcSegment(Base):
    """
    A thermal, glide, or point marker within a track. `start_offset_s` (seconds since
    takeoff) is the load-bearing field for any future video-timeline consumer — never
    return a video-relative offset from this service (architecture.md).
    """

    __tablename__ = "igc_segments"

    id = Column(String, primary_key=True, default=new_uuid)
    track_id = Column(
        String, ForeignKey("igc_tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = Column(String, nullable=False)  # thermal|glide|takeoff|landing|max_alt|top_of_climb
    start_offset_s = Column(Integer, nullable=False)
    start_at = Column(UtcDateTime, nullable=False)
    duration_s = Column(Integer, nullable=True)  # null for the four point-marker kinds
    alt_change_m = Column(Float, nullable=True)  # thermal/glide only
    vertical_velocity_ms = Column(Float, nullable=True)  # thermal only
    glide_ratio = Column(Float, nullable=True)  # glide only


class SiteObservation(Base):
    """
    A single takeoff/landing GPS fix feeding a site's automatic coordinate refinement
    (core/site_backfill.py) — never geocoded, only ever a median of real track fixes. Not
    directly pilot-visible as its own view.
    """

    __tablename__ = "site_observations"

    id = Column(String, primary_key=True, default=new_uuid)
    site_id = Column(String, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(String, ForeignKey("igc_tracks.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)  # takeoff|landing
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    alt_m = Column(Float, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)


class IgcPendingUpload(Base):
    """
    A bulk-uploaded file that didn't auto-attach — ambiguous match or rejected. The file is
    already written to content-addressed storage at upload time, whether or not it resolves
    right away, so resolving later reads stored bytes rather than requiring re-upload. Kept
    (not deleted) once resolved, as a record of what happened to this upload.
    """

    __tablename__ = "igc_pending_uploads"
    __table_args__ = (
        UniqueConstraint("owner_id", "sha256", name="uq_igc_pending_uploads_owner_sha256"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sha256 = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    status = Column(String, nullable=False)  # needs_resolution|rejected
    reason = Column(String, nullable=True)
    candidate_flight_ids_json = Column(Text, nullable=True)
    resolved_flight_id = Column(String, ForeignKey("flights.id"), nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    resolved_at = Column(UtcDateTime, nullable=True)

    owner = relationship("User", back_populates="igc_pending_uploads")


class Hike(Base):
    """
    Fitnessprogramm sheet — a hike, optionally linked to a Hike&Fly-category flight when the
    source row carried an Airtime/Landeplatz value (the real signal that this hike became a
    flight) and the date match against is_hike_fly flights was unambiguous. A pure hike is
    never linked, and that's a complete, valid state on its own — not a to-do.
    """

    __tablename__ = "hikes"
    __table_args__ = (UniqueConstraint("owner_id", "import_key", name="uq_hikes_owner_import_key"),)

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_key = Column(String, nullable=True)  # "fitnessprogramm:<row>"; NULL if entered directly
    hike_date = Column(Date, nullable=False)
    start_place = Column(String, nullable=False)
    destination_place = Column(String, nullable=False)
    ascent_m = Column(Integer, nullable=True)
    descent_m = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    duration_min = Column(Integer, nullable=True)
    route_description = Column(Text, nullable=True)
    flight_id = Column(String, ForeignKey("flights.id"), nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="hikes")


class GroundhandlingSession(Base):
    """Groundhandling sheet. Standalone — never linked to a flight."""

    __tablename__ = "groundhandling_sessions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "import_key", name="uq_groundhandling_sessions_owner_import_key"
        ),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_key = Column(String, nullable=True)  # "groundhandling:<row>"
    session_date = Column(Date, nullable=False)
    place = Column(String, nullable=False)
    duration_min = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="groundhandling_sessions")


class TandemFlight(Base):
    """
    Tandemflüge sheet — the pilot flew as a passenger, never the wing. Deliberately not a row
    in `flights` (architecture.md). `tandem_operator` stays free text, never a Buddy FK — real
    source values include company names (e.g. "AlpineAir"), not just personal contacts.
    """

    __tablename__ = "tandem_flights"
    __table_args__ = (
        UniqueConstraint("owner_id", "import_key", name="uq_tandem_flights_owner_import_key"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_key = Column(String, nullable=True)  # "tandemfluege:<row>"
    flight_date = Column(Date, nullable=False)
    launch_place = Column(String, nullable=False)
    landing_place = Column(String, nullable=False)
    tandem_operator = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    cost = Column(Float, nullable=True)  # 0 is a real, meaningful value — a free tandem
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="tandem_flights")


class Goal(Base):
    """
    Ziele sheet — the one imported type that stays editable afterward, unlike hikes/
    groundhandling/tandem_flights (import-and-view only). difficulty/category/status are
    plain strings, not enums — the observed value sets aren't guaranteed closed.
    """

    __tablename__ = "goals"
    __table_args__ = (UniqueConstraint("owner_id", "import_key", name="uq_goals_owner_import_key"),)

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_key = Column(String, nullable=True)  # "ziele:<row>"; NULL for a goal created directly
    title = Column(String, nullable=False)
    wind_direction = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    links = Column(Text, nullable=True)
    target_season = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)

    owner = relationship("User", back_populates="goals")


class ApiKey(Base):
    """
    A pilot-minted, scoped machine credential (v0.8 — 02-backend-conventions.md's
    "API Keys — hash with SHA-256, not bcrypt"). The plaintext exists only in the creation
    response, never stored — `key_hash` is a one-way SHA-256 digest, `key_prefix` is the
    unique lookup key handed back on every subsequent request via `X-API-Key`.
    """

    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=new_uuid)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False, unique=True, index=True)
    key_hash = Column(String, nullable=False)
    scopes = Column(String, nullable=False)  # space-separated, e.g. "flights:read"
    expires_at = Column(UtcDateTime, nullable=True)  # NULL = never expires
    last_used_at = Column(UtcDateTime, nullable=True)
    revoked_at = Column(UtcDateTime, nullable=True)  # immediate kill switch; wins over expiry
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)

    owner = relationship("User", back_populates="api_keys")


class FlightLink(Base):
    """
    An external resource (e.g. a VidFactory video) an API key pushed back onto a flight it
    could read. Reached only through its parent `flights` row — no `owner_id` of its own,
    same reasoning already applied to `igc_segments` (specs/003-igc-ingest-analysis).
    """

    __tablename__ = "flight_links"
    __table_args__ = (
        UniqueConstraint("flight_id", "kind", "external_id", name="uq_flight_links_identity"),
    )

    id = Column(String, primary_key=True, default=new_uuid)
    flight_id = Column(String, ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)  # e.g. "video" — open-ended, not an enum column
    external_id = Column(String, nullable=False)
    url = Column(String, nullable=False)  # http(s):// only, validated in the Pydantic model
    label = Column(String, nullable=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow)
    updated_at = Column(UtcDateTime, nullable=True, onupdate=utcnow)
