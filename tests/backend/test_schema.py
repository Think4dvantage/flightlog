"""Schema creation and region seeding — the v0.2 foundation every other test builds on."""

from __future__ import annotations

from sqlalchemy import select

from flightlog.database.db import _seed_regions
from flightlog.database.models import Region

EXPECTED_TABLES = {
    "users",
    "regions",
    "sites",
    "user_site_prefs",
    "gliders",
    "harnesses",
    "flight_categories",
    "buddies",
    "flights",
    "flight_buddies",
}


def test_all_v02_tables_are_created(db_engine):
    from sqlalchemy import inspect

    tables = set(inspect(db_engine).get_table_names())
    assert tables >= EXPECTED_TABLES


def test_seed_regions_creates_twelve_rows(db_engine, db_session):
    _seed_regions(db_engine)
    regions = db_session.execute(select(Region)).scalars().all()
    assert len(regions) == 12


def test_seed_regions_is_idempotent(db_engine, db_session):
    _seed_regions(db_engine)
    _seed_regions(db_engine)
    regions = db_session.execute(select(Region)).scalars().all()
    assert len(regions) == 12
