"""
Secondary sheets import (hikes/groundhandling/tandem_flights) against the real
olddata/Flugbuch.xlsx workbook — same real-data-only convention as test_importer.py's
real-workbook section, since these three sheets have no synthetic fixture counterpart.

Hike-to-flight linking needs real flights to link against, so every test here first runs the
primary flight import (core.importer.run_import) to populate flights/categories, then runs the
secondary import on top of the same session.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from flightlog.core.importer import run_import
from flightlog.core.secondary_import import run_secondary_import
from flightlog.database.models import GroundhandlingSession, Hike, TandemFlight

REAL_WORKBOOK_PATH = Path(__file__).parent.parent.parent / "olddata" / "Flugbuch.xlsx"
pytestmark = pytest.mark.skipif(
    not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present"
)


@pytest.fixture
def owner_with_flights(db_session, make_user):
    owner = make_user()
    run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)
    return owner


def test_dry_run_makes_zero_writes(db_session, owner_with_flights):
    report = run_secondary_import(
        db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=False
    )

    assert report.hikes_read == 85
    assert report.hikes_written == 0
    assert report.groundhandling_read == 9
    assert report.groundhandling_written == 0
    assert report.tandem_flights_read == 17
    assert report.tandem_flights_written == 0
    assert db_session.execute(select(Hike)).scalars().all() == []


def test_write_imports_exactly_the_real_row_counts(db_session, owner_with_flights):
    report = run_secondary_import(
        db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True
    )

    assert report.hikes_written == 85
    assert report.groundhandling_written == 9
    assert report.tandem_flights_written == 17

    assert len(db_session.execute(select(Hike)).scalars().all()) == 85
    assert len(db_session.execute(select(GroundhandlingSession)).scalars().all()) == 9
    assert len(db_session.execute(select(TandemFlight)).scalars().all()) == 17


def test_hike_links_to_flight_only_when_unambiguous(db_session, owner_with_flights):
    report = run_secondary_import(
        db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True
    )

    # Confirmed against the real workbook: 35 of 85 hikes link to exactly one same-date
    # Hike&Fly flight; the rest are pure hikes or fell into an ambiguous same-day collision.
    assert report.hikes_linked == 35

    linked = db_session.execute(select(Hike).where(Hike.flight_id.isnot(None))).scalars().all()
    assert len(linked) == 35

    unlinked = db_session.execute(select(Hike).where(Hike.flight_id.is_(None))).scalars().all()
    assert len(linked) + len(unlinked) == 85

    # Every linked hike's own date matches its flight's date exactly — the only signal the
    # matching rule uses.
    from flightlog.database.models import Flight

    for hike in linked:
        flight = db_session.get(Flight, hike.flight_id)
        assert flight.flight_date == hike.hike_date


def test_second_write_run_is_idempotent(db_session, owner_with_flights):
    first = run_secondary_import(
        db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True
    )
    second = run_secondary_import(
        db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True
    )

    assert first.hikes_written == 85
    assert second.hikes_written == 0
    assert second.hikes_skipped_existing == 85
    assert second.groundhandling_skipped_existing == 9
    assert second.tandem_flights_skipped_existing == 17

    assert len(db_session.execute(select(Hike)).scalars().all()) == 85
    assert len(db_session.execute(select(GroundhandlingSession)).scalars().all()) == 9
    assert len(db_session.execute(select(TandemFlight)).scalars().all()) == 17


def test_tandem_flight_cost_of_zero_is_stored_not_dropped(db_session, owner_with_flights):
    run_secondary_import(db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True)

    free_tandems = (
        db_session.execute(select(TandemFlight).where(TandemFlight.cost == 0)).scalars().all()
    )
    # Real workbook has several free (flight-school) tandem flights.
    assert len(free_tandems) > 0
    for t in free_tandems:
        assert t.cost == 0  # not None — a real, meaningful value


def test_tandem_operator_can_be_a_company_name_not_just_a_person(db_session, owner_with_flights):
    run_secondary_import(db_session, str(REAL_WORKBOOK_PATH), owner_with_flights.id, write=True)

    operators = {
        t.tandem_operator
        for t in db_session.execute(select(TandemFlight)).scalars().all()
        if t.tandem_operator
    }
    assert any("AlpineAir" in op for op in operators)
