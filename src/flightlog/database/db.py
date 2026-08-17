"""
Database engine, schema initialisation, column migrations and seeding.

No Alembic. No .sql files. No _migrations table.

- New tables come from `Base.metadata.create_all()`, which is idempotent and runs every
  startup.
- New columns on an existing table get an idempotent `PRAGMA table_info()`-guarded
  `ALTER TABLE` in `_run_column_migrations()`.
- Seeding is a Python list plus an existence check.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from flightlog.database.models import Base, Region, User

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_db(db_path: str) -> Engine:
    """Create the engine, apply pragmas, build the schema, migrate and seed."""
    global _engine, _SessionLocal

    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
    else:
        url = "sqlite:///:memory:"

    _engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver callback
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    Base.metadata.create_all(bind=_engine)

    with _engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    logger.info("Database initialised at %s (journal_mode=%s)", db_path, mode)

    _run_column_migrations(_engine)
    _seed_regions(_engine)

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


# Transcribed once from the legacy workbook's "Flight Area" SUM formulas — the mapping only
# exists implicitly there as which Launch Statistics rows each region's formula references.
# See specs/001-core-data-import/research.md. Order matches the workbook's own row order.
_REGIONS = [
    "Interlaken",
    "Mürren",
    "Grindelwald",
    "Gantrischgebiet",
    "Jura",
    "Brienz",
    "Niesen",
    "Adelboden-Lenk",
    "Marbach",
    "Schwarzsee",
    "Därstetten",
    "Fiesch",
]


def _seed_regions(engine: Engine) -> None:
    """Shared reference data, not owner-scoped. A Python list plus an existence check — never
    a .sql fixture. Safe to re-run."""
    with Session(engine) as db:
        seeded = 0
        for order, name in enumerate(_REGIONS):
            if db.execute(select(Region.id).where(Region.name == name)).first() is not None:
                continue
            db.add(Region(name=name, sort_order=order))
            seeded += 1
        db.commit()
        logger.info("Seeded regions: %d added, %d already present", seeded, len(_REGIONS) - seeded)


def _run_column_migrations(engine: Engine) -> None:
    """
    Add columns introduced after a table's initial schema. Safe to re-run.

    NEVER Alembic. NEVER .sql files. NEVER a _migrations table.
    """
    applied = 0
    with engine.connect() as conn:
        flight_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(flights)")).fetchall()
        }
        if "visibility" not in flight_cols:
            conn.execute(
                text("ALTER TABLE flights ADD COLUMN visibility VARCHAR NOT NULL DEFAULT 'private'")
            )
            conn.commit()
            logger.info("Migration: added flights.visibility column")
            applied += 1

        if "nickname" not in flight_cols:
            conn.execute(text("ALTER TABLE flights ADD COLUMN nickname VARCHAR"))
            conn.commit()
            logger.info("Migration: added flights.nickname column")
            applied += 1

        user_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        if "public_profile_enabled" not in user_cols:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN public_profile_enabled BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
            logger.info("Migration: added users.public_profile_enabled column")
            applied += 1

    logger.info("Column migrations: %d applied, schema up to date", applied)


def seed_bootstrap_admin(engine: Engine, email: str, password: str) -> None:
    """
    Create the first admin account. Skipped entirely if any user already exists, so it
    cannot resurrect a deliberately deleted account or overwrite a changed password.
    """
    if not email or not password:
        logger.info("Bootstrap admin: not configured, skipping")
        return

    # Imported here rather than at module scope: services.auth imports config, and
    # importing it at module load would make db.py's import order matter.
    from flightlog.services.auth import hash_password

    with Session(engine) as db:
        if db.execute(select(User.id).limit(1)).first() is not None:
            logger.info("Bootstrap admin: users already exist, skipping")
            return

        db.add(
            User(
                email=email.lower().strip(),
                display_name=email.split("@")[0],
                hashed_password=hash_password(password),
                role="admin",
            )
        )
        db.commit()
        logger.info("Bootstrap admin created: %s", email)


def get_db():
    """FastAPI dependency. Sync (`def`) — which is why tests need StaticPool."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() during startup")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> sessionmaker:
    """For callers outside the request cycle (CLI importers, background work)."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() during startup")
    return _SessionLocal


def check_db_health(engine: Engine | None = None) -> str:
    """
    Return 'ok' or a short failure reason. Never raises — the health route needs both.

    Takes the engine as an argument rather than reading module state, so the health route
    can pass `app.state.engine`. Reaching into `_engine` here would make the check report
    "not initialised" for any caller that wired its own engine.
    """
    target = engine or _engine
    if target is None:
        return "not initialised"
    try:
        with target.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc, exc_info=True)
        return f"error: {type(exc).__name__}"
