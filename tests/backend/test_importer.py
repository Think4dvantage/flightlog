"""
Importer tests against the synthetic fixture workbook (tests/fixtures/flugbuch_sample.xlsx),
which uses real canonical names from core/aliases.py's tables since the aliaser is hardcoded to
the actual legacy workbook's reference data, not a generic normalizer. See
specs/001-core-data-import/research.md for the fixture's design and the real-data findings it
mirrors.

The one test that reads olddata/Flugbuch.xlsx directly (the real 600-flight workbook) lives at
the bottom of this file, clearly separated — see plan.md's Risk section for why it's a deliberate
exception and needs removal/replacement before the v0.8 history scrub.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from flightlog.core.importer import run_import
from flightlog.database.models import Buddy, Flight, FlightCategory, Glider, Harness, Site

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "flugbuch_sample.xlsx"
REAL_WORKBOOK_PATH = Path(__file__).parent.parent.parent / "olddata" / "Flugbuch.xlsx"


@pytest.fixture
def owner(make_user):
    return make_user()


def test_dry_run_makes_zero_writes(db_session, owner):
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    assert report.flights_written == 0
    assert db_session.execute(select(Flight)).scalars().all() == []
    assert db_session.execute(select(Site)).scalars().all() == []


def test_write_creates_expected_entities(db_session, owner):
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    # 5 rows total, 1 unresolvable category (row 5) -> 4 flights written
    assert report.rows_read == 5
    assert report.flights_written == 4
    assert len(report.flights_skipped_unresolved) == 1
    assert report.flights_skipped_unresolved[0]["reason"] == "category"
    assert report.flights_skipped_unresolved[0]["value"] == "UnknownCategoryXYZ"

    flights = db_session.execute(select(Flight)).scalars().all()
    assert len(flights) == 4


def test_alias_resolution_hits_the_canonical_name(db_session, owner):
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    assert ("BergBo", "Bergbo") in report.alias_hits["site"]
    site = db_session.execute(select(Site).where(Site.name == "Bergbo")).scalar_one()
    assert site is not None
    # No site named with the raw alias value should ever be created
    assert db_session.execute(select(Site).where(Site.name == "BergBo")).first() is None


def test_unresolved_category_never_creates_a_flight_or_a_category(db_session, owner):
    run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    bad_category = db_session.execute(
        select(FlightCategory).where(FlightCategory.name == "UnknownCategoryXYZ")
    ).first()
    assert bad_category is None


def test_gear_and_sites_are_created_from_the_fixture(db_session, owner):
    run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    gliders = db_session.execute(select(Glider)).scalars().all()
    harnesses = db_session.execute(select(Harness)).scalars().all()
    sites = db_session.execute(select(Site)).scalars().all()

    assert len(gliders) == 1
    assert gliders[0].model == "Advance Alpha 6 28"
    assert len(harnesses) == 1
    assert harnesses[0].model == "Advance Easyness 1"
    # Hohwald, Bergbo, Fiescheralp (launches) + Höhenmatte (landing) = 4 distinct sites
    assert len(sites) == 4


def test_owner_id_on_imported_rows_always_comes_from_the_caller_never_source_data(
    db_session, owner
):
    run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    flights = db_session.execute(select(Flight)).scalars().all()
    assert all(f.owner_id == owner.id for f in flights)
    sites = db_session.execute(select(Site)).scalars().all()
    assert all(s.owner_id == owner.id for s in sites)


def test_region_reconciliation_reports_the_deliberate_mismatch(db_session, owner):
    """The fixture's Übersicht sheet claims Interlaken=2, but Hohwald/Hohwald/Bergbo (rows
    2-4) all resolve to Interlaken via SITE_REGION — a computed count of 3."""
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    assert report.region_mismatches["Interlaken"] == {"computed": 3, "sheet": 2}


def test_altgain_cross_check_reports_the_deliberate_mismatch(db_session, owner):
    """Row 2: max_alt(1700) - launch_elev(1580) = 120, but the sheet's Altgain column says
    999 — a deliberate mismatch built into the fixture."""
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    mismatch = next(m for m in report.altgain_mismatches if m["row"] == 2)
    assert mismatch["computed_alt_gain_m"] == 120
    assert mismatch["sheet_altgain"] == 999
    assert mismatch["delta"] == 120 - 999


def test_region_and_altgain_checks_run_even_without_write(db_session, owner):
    """A trustworthy dry-run report must not require --write first (FR-015/FR-016)."""
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    assert report.flights_written == 0
    assert report.region_mismatches  # still populated despite no writes
    assert report.altgain_mismatches


def test_buddy_mentions_are_proposed_but_never_auto_created(db_session, owner):
    """Row 2 mentions 'Tom', row 4 mentions 'Ueli' — both real KNOWN_BUDDY_NAMES entries.
    FR-017: a proposal never creates a buddies row."""
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    assert report.buddy_proposals["Tom"] == 1
    assert report.buddy_proposals["Ueli"] == 1
    assert db_session.execute(select(Buddy)).scalars().all() == []


def test_buddy_proposals_run_even_without_write(db_session, owner):
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    assert report.buddy_proposals["Tom"] == 1
    assert report.buddy_proposals["Ueli"] == 1


def test_unknown_names_in_comments_are_not_proposed(db_session, owner):
    """'Hohwald' (a site name, not a buddy) and other comment words must never surface as
    proposals just because they're capitalized — only KNOWN_BUDDY_NAMES entries count."""
    report = run_import(db_session, str(FIXTURE_PATH), owner.id, write=False)

    assert "Hohwald" not in report.buddy_proposals
    assert "Advance" not in report.buddy_proposals


def test_running_write_twice_is_a_no_op_the_second_time(db_session, owner):
    """FR-012: a second --write run against the same file leaves every count unchanged."""
    first = run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)
    second = run_import(db_session, str(FIXTURE_PATH), owner.id, write=True)

    assert first.flights_written == 4
    assert second.flights_written == 0
    assert second.flights_skipped_existing == 4
    assert second.sites_written == 0
    assert second.gliders_written == 0
    assert second.harnesses_written == 0
    assert second.categories_written == 0

    flights = db_session.execute(select(Flight)).scalars().all()
    sites = db_session.execute(select(Site)).scalars().all()
    assert len(flights) == 4
    assert len(sites) == 4


# ---------------------------------------------------------------------------------------
# Real-data regression tests. Read olddata/Flugbuch.xlsx directly — see module docstring.
# ---------------------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_real_workbook_imports_exactly_600_flights(db_session, owner):
    report = run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    # 3 flights use "Advance Success 2", a harness absent from DropDownData's current
    # master list — retired gear, not a typo (research.md). It does not block the flight;
    # only glider/harness resolution failures leave that field null. All 600 rows resolve
    # a launch site and a category, so all 600 become flights.
    assert report.rows_read == 600
    assert report.flights_written == 600

    flights = db_session.execute(select(Flight)).scalars().all()
    assert len(flights) == 600


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_real_workbook_region_reconciliation_reproduces_the_known_gap(db_session, owner):
    """
    research.md's confirmed finding: the Total-column region formulas in Übersicht fell
    out of sync when three launch sites were added, but only two of the three made it
    into the yearly formulas. Fiescheralp is genuinely unreferenced anywhere and is
    expected to show as a residual mismatch; Interlaken and Grindelwald mismatch too,
    in the opposite direction, because this project's SITE_REGION mapping (reconstructed
    from the more complete yearly formulas) counts more launches for them than the
    stale Total column does.
    """
    report = run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert report.region_mismatches["Fiesch"] == {"computed": 0, "sheet": 1}
    assert (
        report.region_mismatches["Interlaken"]["computed"]
        > report.region_mismatches["Interlaken"]["sheet"]
    )
    assert (
        report.region_mismatches["Grindelwald"]["computed"]
        > report.region_mismatches["Grindelwald"]["sheet"]
    )


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_real_workbook_altgain_cross_check_finds_exactly_one_mismatch(db_session, owner):
    """research.md / plan.md's Risk section: across 600 real flights, exactly one row
    (387) has a stored Altgain that disagrees with computed max_alt - launch_elev."""
    report = run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert len(report.altgain_mismatches) == 1
    assert report.altgain_mismatches[0]["row"] == 387


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_real_workbook_second_write_run_still_yields_exactly_600_flights(db_session, owner):
    """FR-012, against the real data: a second --write run is a no-op, not a duplication."""
    run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)
    second = run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert second.flights_written == 0
    assert second.flights_skipped_existing == 600

    flights = db_session.execute(select(Flight)).scalars().all()
    assert len(flights) == 600


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_real_workbook_buddy_proposals_match_known_names_never_auto_create(db_session, owner):
    """KNOWN_BUDDY_NAMES was derived from real frequency analysis of this exact workbook's
    Kommentar column (research.md) — every name in it must actually appear, and nothing
    is ever auto-created regardless of how often a name is mentioned."""
    report = run_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert report.buddy_proposals["Tom"] > 0
    assert report.buddy_proposals["Ueli"] > 0
    assert db_session.execute(select(Buddy)).scalars().all() == []
