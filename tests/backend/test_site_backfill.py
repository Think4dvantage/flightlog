"""Site coordinate auto-backfill: median at the >=3 threshold, manual pins never overwritten,
dropping back below threshold on detach clears the auto-set coordinate."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
# Three distinct files (different sha256) sharing the same launch point by construction
# (tests/backend/fixtures were generated from the same base coordinates) — a real median
# recompute needs the UniqueConstraint("owner_id", "sha256") on igc_tracks to allow three
# different flights, so identical file content can't be reused across flights.
FILE_A = (FIXTURES / "valid_flight.igc").read_bytes()
FILE_B = (FIXTURES / "sameday_flight_a.igc").read_bytes()
FILE_C = (FIXTURES / "sameday_flight_b.igc").read_bytes()


@pytest.fixture
def site_and_flights(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Site

    user = make_user()
    site = Site(owner_id=user.id, name="Launch", is_launch=True)  # no coords yet
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([site, category])
    db_session.commit()

    flights = []
    for d in [date(2024, 8, 15), date(2024, 9, 1), date(2024, 9, 2)]:
        f = Flight(owner_id=user.id, flight_date=d, launch_site_id=site.id, category_id=category.id)
        db_session.add(f)
        flights.append(f)
    db_session.commit()
    return user, site, flights


async def test_site_gets_real_coords_after_three_tracks(
    client, make_token, site_and_flights, db_session
):
    user, site, flights = site_and_flights
    headers = make_token(user=user)

    for flight, data, name in zip(
        flights, [FILE_A, FILE_B, FILE_C], ["a.igc", "b.igc", "c.igc"], strict=True
    ):
        resp = await client.post(
            f"/api/flights/{flight.id}/igc",
            files={"file": (name, data, "application/octet-stream")},
            headers=headers,
        )
        assert resp.status_code == 200

    db_session.refresh(site)
    assert site.coord_source == "igc_median"
    assert site.lat == pytest.approx(46.68, abs=0.01)
    assert site.lon == pytest.approx(7.85, abs=0.01)
    assert site.coord_accuracy_m is not None


async def test_manual_pin_is_never_overwritten(client, make_token, site_and_flights, db_session):
    from flightlog.database.models import Site

    user, site, flights = site_and_flights
    site.lat, site.lon, site.coord_source = 40.0, 8.0, "manual"
    db_session.commit()
    headers = make_token(user=user)

    for flight, data, name in zip(
        flights, [FILE_A, FILE_B, FILE_C], ["a.igc", "b.igc", "c.igc"], strict=True
    ):
        resp = await client.post(
            f"/api/flights/{flight.id}/igc",
            files={"file": (name, data, "application/octet-stream")},
            headers=headers,
        )
        assert resp.status_code == 200

    refreshed = db_session.get(Site, site.id)
    assert refreshed.coord_source == "manual"
    assert refreshed.lat == 40.0
    assert refreshed.lon == 8.0


async def test_detach_below_threshold_clears_auto_coords(
    client, make_token, site_and_flights, db_session
):
    from flightlog.database.models import Site

    user, site, flights = site_and_flights
    headers = make_token(user=user)

    for flight, data, name in zip(
        flights, [FILE_A, FILE_B, FILE_C], ["a.igc", "b.igc", "c.igc"], strict=True
    ):
        await client.post(
            f"/api/flights/{flight.id}/igc",
            files={"file": (name, data, "application/octet-stream")},
            headers=headers,
        )

    detached = await client.delete(f"/api/flights/{flights[0].id}/igc", headers=headers)
    assert detached.status_code == 204

    refreshed = db_session.get(Site, site.id)
    assert refreshed.coord_source is None
    assert refreshed.lat is None
    assert refreshed.lon is None
