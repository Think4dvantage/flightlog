"""
Statistics — pure-logic unit tests (duck-typed, DB-free per 06-testing-conventions.md) plus
API tests against a small hand-built fixture set (ties, a "not recorded" dimension bucket,
zero-track and zero-buddy states) rather than the real 600-flight workbook, since this
feature needs specific known edge cases more than realistic scale (plan.md).
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from flightlog.core.stats import (
    current_streak,
    hike_fly_total,
    launch_technique_split,
    ytd_pace,
)
from flightlog.database.models import utcnow

# ---- pure-logic tests: no DB, no client ----


def _f(flight_date, launch_technique=None, is_hike_fly=False, flight_id="f"):
    return SimpleNamespace(
        id=flight_id,
        flight_date=flight_date,
        launch_technique=launch_technique,
        is_hike_fly=is_hike_fly,
    )


def test_reverse_share_counts_every_flight():
    """Pinned example from 06-testing-conventions.md — must keep passing verbatim."""
    flights = [_f(date(2026, 1, 1), "reverse"), _f(date(2026, 1, 2), "forward")]
    assert launch_technique_split(flights)["reverse_pct"] == 50.0


def test_launch_technique_split_empty_is_zero_not_a_crash():
    assert launch_technique_split([]) == {"forward": 0, "reverse": 0, "reverse_pct": 0.0}


def test_hike_fly_total_counts_only_flagged_flights():
    flights = [
        _f(date(2026, 1, 1), is_hike_fly=True),
        _f(date(2026, 1, 2), is_hike_fly=False),
    ]
    assert hike_fly_total(flights) == 1


def test_current_streak_counts_consecutive_weeks_ending_today():
    today = utcnow().date()
    flights = [
        _f(today, flight_id="a"),
        _f(today - timedelta(days=7), flight_id="b"),
        _f(today - timedelta(days=14), flight_id="c"),
    ]
    assert current_streak(flights, today) == {"unit": "week", "count": 3}


def test_current_streak_is_broken_once_stale():
    today = utcnow().date()
    flights = [_f(today - timedelta(days=21), flight_id="a")]
    assert current_streak(flights, today) == {"unit": "week", "count": 0}


def test_current_streak_empty_flights_is_zero():
    assert current_streak([], utcnow().date()) == {"unit": "week", "count": 0}


def test_ytd_pace_compares_same_calendar_window():
    today = utcnow().date()
    prior_cutoff = today.replace(year=today.year - 1)
    flights = [
        _f(today, flight_id="a"),
        _f(prior_cutoff, flight_id="b"),
        _f(prior_cutoff + timedelta(days=1), flight_id="c"),  # one day past the window
    ]
    assert ytd_pace(flights, today) == {"this_year": 1, "same_point_prior_year": 1}


# ---- API tests ----


@pytest.fixture
def stats_setup(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Glider, Harness, Site

    user = make_user()
    launch_a = Site(owner_id=user.id, name="Launch A", is_launch=True, elevation_m=1500)
    launch_b = Site(owner_id=user.id, name="Launch B", is_launch=True, elevation_m=1800)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True, elevation_m=1000)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    training_category = FlightCategory(
        owner_id=user.id, name="Training", slug="training", is_training=True
    )
    glider = Glider(owner_id=user.id, brand="Ozone", model="Rush", size="MS")
    harness = Harness(owner_id=user.id, brand="Advance", model="Impress")
    db_session.add_all([launch_a, launch_b, landing, category, training_category, glider, harness])
    db_session.commit()

    def make_flight(**kwargs):
        defaults = {"owner_id": user.id, "launch_site_id": launch_a.id, "category_id": category.id}
        defaults.update(kwargs)
        flight = Flight(**defaults)
        db_session.add(flight)
        db_session.commit()
        db_session.refresh(flight)
        return flight

    # f1/f2 tie for max_altitude (2000m) — f1 is earlier, so it must win the tie-break.
    f1 = make_flight(
        flight_date=date(2023, 5, 1),
        landing_site_id=landing.id,
        glider_id=glider.id,
        harness_id=harness.id,
        max_alt_m=2000,
        duration_min=90,
        distance_km=20.0,
        launch_technique="forward",
    )
    f2 = make_flight(
        flight_date=date(2023, 6, 1),
        landing_site_id=landing.id,
        glider_id=glider.id,
        harness_id=harness.id,
        max_alt_m=2000,
        duration_min=60,
        distance_km=15.0,
        launch_technique="reverse",
    )
    # f3: a different launch site, and missing glider/harness/landing site entirely —
    # the "not recorded" bucket case (spec.md's Edge Cases).
    f3 = make_flight(
        flight_date=date(2023, 7, 1),
        launch_site_id=launch_b.id,
        max_alt_m=1900,
        duration_min=45,
        distance_km=10.0,
        launch_technique="forward",
    )
    # f4: training-flagged, excluded from avg_airtime_min_excl_training.
    f4 = make_flight(
        flight_date=date(2023, 8, 1),
        category_id=training_category.id,
        landing_site_id=landing.id,
        glider_id=glider.id,
        harness_id=harness.id,
        max_alt_m=1700,
        duration_min=200,
        distance_km=5.0,
        launch_technique="reverse",
    )

    return SimpleNamespace(
        user=user,
        launch_a=launch_a,
        launch_b=launch_b,
        landing=landing,
        category=category,
        training_category=training_category,
        glider=glider,
        harness=harness,
        flights=[f1, f2, f3, f4],
    )


async def test_totals(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    resp = await client.get("/api/stats/totals", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_flights"] == 4
    assert body["total_airtime_min"] == 395
    assert body["total_distance_km"] == 50.0
    assert body["total_alt_gain_m"] == 1300  # 500 + 500 + 100 + 200
    assert body["avg_airtime_min"] == pytest.approx(98.75)
    assert body["avg_airtime_min_excl_training"] == pytest.approx(65.0)  # excludes f4 (training)
    assert body["avg_distance_km"] == pytest.approx(12.5)


async def test_time_breakdown(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/time-breakdown", headers=headers)).json()
    assert body["by_year"] == {"2023": 4}
    assert body["by_month"] == {"5": 1, "6": 1, "7": 1, "8": 1}
    assert body["year_month_matrix"] == {"2023": {"5": 1, "6": 1, "7": 1, "8": 1}}


async def test_distribution_buckets(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/distribution", headers=headers)).json()
    assert body["duration_buckets"] == {
        "<30min": 0,
        "30-60min": 1,
        "60-120min": 2,
        "120-180min": 0,
        ">180min": 1,
    }
    assert body["distance_buckets"] == {
        "<10km": 1,
        "10-25km": 3,
        "25-50km": 0,
        "50-100km": 0,
        ">100km": 0,
    }
    assert body["altitude_buckets"] == {
        "<200m": 1,
        "200-500m": 1,
        "500-1000m": 2,
        "1000-2000m": 0,
        ">2000m": 0,
    }


async def test_monthly_extremes(client, make_token, stats_setup):
    """Max per calendar month across all years — not an average; an untouched month is null."""
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/monthly-extremes", headers=headers)).json()

    assert body["max_duration_min_by_month"]["5"] == 90  # f1
    assert body["max_duration_min_by_month"]["6"] == 60  # f2
    assert body["max_duration_min_by_month"]["7"] == 45  # f3
    assert body["max_duration_min_by_month"]["8"] == 200  # f4
    assert body["max_duration_min_by_month"]["1"] is None  # no January flight

    assert body["max_distance_km_by_month"]["5"] == 20.0
    assert body["max_alt_gain_m_by_month"]["5"] == 500  # tied with June, both included per-month


async def test_airtime_by_month(client, make_token, stats_setup, db_session):
    """Combined across every year (not per-year), and each month keeps every contributing
    flight's own duration — largest first — rather than just the pre-summed total, since the
    frontend stacks them into one bar per month."""
    from flightlog.database.models import Flight

    # A second May flight, a different year, to exercise both cross-year combination and
    # within-month stacking/ordering.
    extra = Flight(
        owner_id=stats_setup.user.id,
        launch_site_id=stats_setup.launch_a.id,
        landing_site_id=stats_setup.landing.id,
        category_id=stats_setup.category.id,
        flight_date=date(2024, 5, 15),
        duration_min=30,
    )
    db_session.add(extra)
    db_session.commit()

    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/airtime-by-month", headers=headers)).json()

    assert body["by_month"]["5"] == [90, 30]  # f1 (2023) + extra (2024), largest-first
    assert body["total_by_month"]["5"] == 120
    assert body["by_month"]["6"] == [60]  # f2
    assert body["total_by_month"]["6"] == 60
    assert body["by_month"]["1"] == []  # no January flight at all
    assert body["total_by_month"]["1"] == 0


async def test_personal_bests_tie_resolves_to_earliest_flight(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/personal-bests", headers=headers)).json()
    by_label = {row["label"]: row for row in body}

    assert len(body) == 8
    assert by_label["max_altitude"]["value"] == 2000
    assert by_label["max_altitude"]["flight_id"] == stats_setup.flights[0].id  # f1, tied with f2
    assert by_label["max_altitude"]["flight_date"] == "2023-05-01"
    assert by_label["longest_airtime"]["flight_id"] == stats_setup.flights[3].id  # f4
    assert by_label["highest_launch"]["flight_id"] == stats_setup.flights[2].id  # f3 (launch_b)
    assert by_label["shortest_distance"]["flight_id"] == stats_setup.flights[3].id  # f4


async def test_xc_progression_uses_distance_threshold_not_category_name(
    client, make_token, stats_setup
):
    """f1/f2/f3 are >=10km (the default threshold); f4 (5km) is not — all four are 2023."""
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/xc-progression", headers=headers)).json()

    assert body["threshold_km"] == 10.0
    assert body["rows"] == [
        {"year": 2023, "total_flights": 4, "xc_shaped_flights": 3, "xc_pct": 75.0}
    ]


async def test_matrix_glider_not_recorded_bucket(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/matrix/glider", headers=headers)).json()
    rows = {row["id"]: row for row in body["rows"]}

    assert rows[stats_setup.glider.id]["total"] == 3  # f1, f2, f4
    assert rows[None]["total"] == 1  # f3 — glider not recorded
    assert rows[None]["name"] is None


async def test_matrix_site_never_has_a_not_recorded_bucket(client, make_token, stats_setup):
    """launch_site_id is NOT NULL — every flight resolves to a real site."""
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/matrix/site", headers=headers)).json()
    rows = {row["id"]: row for row in body["rows"]}

    assert None not in rows
    assert rows[stats_setup.launch_a.id]["total"] == 3
    assert rows[stats_setup.launch_b.id]["total"] == 1


async def test_matrix_category(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/matrix/category", headers=headers)).json()
    rows = {row["id"]: row for row in body["rows"]}

    assert rows[stats_setup.category.id]["total"] == 3
    assert rows[stats_setup.training_category.id]["total"] == 1


async def test_matrix_unknown_dimension_is_404_not_422(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    resp = await client.get("/api/stats/matrix/nonsense", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ENTITY_NOT_FOUND"


async def test_matrix_buddy_starts_sparse_then_reflects_a_new_tag(
    client, make_token, stats_setup, db_session
):
    """Only ever `flight_buddies` rows that exist at query time — never backfilled."""
    from flightlog.database.models import Buddy, FlightBuddy

    headers = make_token(user=stats_setup.user)

    empty = (await client.get("/api/stats/matrix/buddy", headers=headers)).json()
    assert empty["rows"] == []

    buddy = Buddy(owner_id=stats_setup.user.id, display_name="Tom")
    db_session.add(buddy)
    db_session.commit()
    db_session.add(FlightBuddy(flight_id=stats_setup.flights[0].id, buddy_id=buddy.id))
    db_session.commit()

    populated = (await client.get("/api/stats/matrix/buddy", headers=headers)).json()
    assert populated["rows"] == [
        {"id": buddy.id, "name": "Tom", "by_year": {"2023": 1}, "total": 1}
    ]


_EMPTY_MONTHS = {str(m): None for m in range(1, 13)}


async def test_igc_rollup_zero_state(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/igc-rollup", headers=headers)).json()
    assert body == {
        "cumulative_thermal_climb_m": 0.0,
        "tracks_uploaded": 0,
        "total_thermals": 0,
        "total_igc_airtime_min": 0.0,
        "avg_thermals_by_month": _EMPTY_MONTHS,
    }


async def test_igc_rollup_sums_thermal_segments_only(client, make_token, stats_setup, db_session):
    """No extra filtering needed (research.md) — but a glide segment must not be counted."""
    from flightlog.database.models import IgcSegment, IgcTrack

    headers = make_token(user=stats_setup.user)
    track = IgcTrack(
        owner_id=stats_setup.user.id,
        flight_id=stats_setup.flights[0].id,
        original_filename="track.igc",
        sha256="a" * 64,
        file_path="irrelevant",
        analyzer_version="test",
        analyzed_at=utcnow(),
    )
    db_session.add(track)
    db_session.commit()
    db_session.add_all(
        [
            IgcSegment(
                track_id=track.id,
                kind="thermal",
                start_offset_s=0,
                start_at=utcnow(),
                alt_change_m=300.0,
            ),
            IgcSegment(
                track_id=track.id,
                kind="glide",
                start_offset_s=600,
                start_at=utcnow(),
                alt_change_m=-50.0,
            ),
        ]
    )
    db_session.commit()

    body = (await client.get("/api/stats/igc-rollup", headers=headers)).json()
    assert body == {
        "cumulative_thermal_climb_m": 300.0,
        "tracks_uploaded": 1,
        "total_thermals": 0,
        "total_igc_airtime_min": 0.0,
        "avg_thermals_by_month": _EMPTY_MONTHS,
    }


async def test_igc_rollup_total_thermals_and_airtime(client, make_token, stats_setup, db_session):
    """`total_thermals`/`total_igc_airtime_min` are plain SUMs over igc_tracks; the
    per-calendar-month average must average across flights within the same month, not just
    sum them (two May tracks: 4 and 2 thermals -> avg 3.0), and leave months with no
    IGC-analyzed flight as null, not zero."""
    from flightlog.database.models import Flight, IgcTrack

    headers = make_token(user=stats_setup.user)

    extra_may_flight = Flight(
        owner_id=stats_setup.user.id,
        launch_site_id=stats_setup.launch_a.id,
        category_id=stats_setup.category.id,
        flight_date=date(2023, 5, 15),
    )
    db_session.add(extra_may_flight)
    db_session.commit()

    def make_track(flight, thermal_count, duration_s, sha):
        return IgcTrack(
            owner_id=stats_setup.user.id,
            flight_id=flight.id,
            original_filename="track.igc",
            sha256=sha * 64,
            file_path="irrelevant",
            analyzer_version="test",
            analyzed_at=utcnow(),
            thermal_count=thermal_count,
            duration_s=duration_s,
        )

    db_session.add_all(
        [
            make_track(stats_setup.flights[0], 4, 3600, "a"),  # May
            make_track(extra_may_flight, 2, 1800, "b"),  # May
            make_track(stats_setup.flights[1], 6, 5400, "c"),  # June
        ]
    )
    db_session.commit()

    body = (await client.get("/api/stats/igc-rollup", headers=headers)).json()
    assert body["total_thermals"] == 12
    assert body["total_igc_airtime_min"] == 180.0
    assert body["avg_thermals_by_month"]["5"] == 3.0
    assert body["avg_thermals_by_month"]["6"] == 6.0
    assert body["avg_thermals_by_month"]["1"] is None


async def test_launch_technique_and_hike_fly(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/launch-technique", headers=headers)).json()
    assert body == {"forward": 2, "reverse": 2, "reverse_pct": 50.0, "hike_fly_total": 0}


async def test_progression_shape(client, make_token, stats_setup):
    headers = make_token(user=stats_setup.user)
    body = (await client.get("/api/stats/progression", headers=headers)).json()
    # All fixture flights are in 2023 — no streak against "today".
    assert body["current_streak"] == {"unit": "week", "count": 0}
    assert "cumulative_series" not in body  # replaced by the frontend's per-year chart
    # f4 (2023-08-01) is the most recent fixture flight; "today" is the real clock, so only
    # the deterministic last_flight_date is asserted, not the day count itself.
    assert body["last_flight_date"] == "2023-08-01"
    assert isinstance(body["days_since_last_flight"], int)
    assert body["days_since_last_flight"] > 0


async def test_zero_state_for_a_brand_new_account(client, make_token):
    headers = make_token()
    totals = (await client.get("/api/stats/totals", headers=headers)).json()
    assert totals["total_flights"] == 0
    assert totals["avg_airtime_min"] == 0.0

    assert (await client.get("/api/stats/personal-bests", headers=headers)).json() == []
    assert (await client.get("/api/stats/matrix/site", headers=headers)).json()["rows"] == []
    igc = (await client.get("/api/stats/igc-rollup", headers=headers)).json()
    assert igc == {
        "cumulative_thermal_climb_m": 0.0,
        "tracks_uploaded": 0,
        "total_thermals": 0,
        "total_igc_airtime_min": 0.0,
        "avg_thermals_by_month": _EMPTY_MONTHS,
    }

    monthly = (await client.get("/api/stats/monthly-extremes", headers=headers)).json()
    assert all(v is None for v in monthly["max_duration_min_by_month"].values())
    assert len(monthly["max_duration_min_by_month"]) == 12

    xc = (await client.get("/api/stats/xc-progression", headers=headers)).json()
    assert xc["rows"] == []

    progression = (await client.get("/api/stats/progression", headers=headers)).json()
    assert progression["days_since_last_flight"] is None
    assert progression["last_flight_date"] is None


async def test_ownership_scoping_another_users_flights_never_leak_in(
    client, make_token, stats_setup
):
    other_headers = make_token(email="other@example.com")
    totals = (await client.get("/api/stats/totals", headers=other_headers)).json()
    assert totals["total_flights"] == 0
