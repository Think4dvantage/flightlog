"""Single-flight IGC upload: analysis figures, dedup no-op, replace, rejection, detach."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
VALID_IGC = (FIXTURES / "valid_flight.igc").read_bytes()
NO_BARO_IGC = (FIXTURES / "no_baro_flight.igc").read_bytes()
CORRUPT_IGC = (FIXTURES / "corrupt.igc").read_bytes()


@pytest.fixture
def base_entities(db_session, make_user):
    """A pilot with a launch site, landing site and category, ready to attach a flight to."""
    from flightlog.database.models import FlightCategory, Site

    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True, elevation_m=1500)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True, elevation_m=1000)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, landing, category])
    db_session.commit()
    return user, launch, landing, category


@pytest.fixture
def flight(db_session, base_entities):
    from flightlog.database.models import Flight

    user, launch, landing, category = base_entities
    f = Flight(
        owner_id=user.id,
        flight_date=date(2024, 8, 15),
        launch_site_id=launch.id,
        landing_site_id=landing.id,
        category_id=category.id,
    )
    db_session.add(f)
    db_session.commit()
    return f


async def test_upload_attaches_track_and_computes_figures(
    client, make_token, base_entities, flight
):
    user = base_entities[0]
    headers = make_token(user=user)

    resp = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["flight_id"] == flight.id
    assert body["duration_s"] == 602
    assert body["thermal_count"] == 1
    assert body["best_climb_ms"] > 0
    assert body["glide_ratio"] > 0
    assert body["alt_source"] == "PRESS"

    fetched = await client.get(f"/api/flights/{flight.id}/igc", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    segments = await client.get(f"/api/flights/{flight.id}/igc/segments", headers=headers)
    assert segments.status_code == 200
    kinds = {s["kind"] for s in segments.json()}
    assert {"takeoff", "landing", "thermal", "glide", "max_alt", "top_of_climb"} <= kinds

    geojson = await client.get(f"/api/flights/{flight.id}/igc/track.geojson", headers=headers)
    assert geojson.status_code == 200
    gj = geojson.json()
    assert gj["type"] == "Feature"
    assert gj["geometry"]["type"] == "LineString"
    assert len(gj["geometry"]["coordinates"]) == len(gj["properties"]["offsets_s"])
    assert len(gj["geometry"]["coordinates"]) > 0


async def test_upload_calibrates_altitude_to_known_launch_elevation(
    client, make_token, db_session, make_user
):
    """End-to-end version of the pilot's own reported case: the fixture's real barometric
    takeoff reading is 1900m; a launch site known to sit at 2000m should shift every absolute
    altitude figure by the same +100m, leave alt_gain_igc_m alone, and — critically — must
    still record the *raw* 1900m into site_observations, not the calibrated 2000m, or the
    site's own elevation_igc_m comparison would become tautological."""
    from flightlog.database.models import Flight, FlightCategory, Site, SiteObservation

    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True, elevation_m=2000)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, category])
    db_session.commit()

    f = Flight(
        owner_id=user.id,
        flight_date=date(2024, 8, 15),
        launch_site_id=launch.id,
        category_id=category.id,
    )
    db_session.add(f)
    db_session.commit()

    headers = make_token(user=user)
    resp = await client.post(
        f"/api/flights/{f.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["alt_calibration_offset_m"] == 100.0  # 2000 - 1900
    assert body["max_alt_igc_m"] == 2531  # uncalibrated 2431 + 100
    assert body["alt_gain_igc_m"] == 531  # a difference — unaffected by the shift

    geojson = await client.get(f"/api/flights/{f.id}/igc/track.geojson", headers=headers)
    first_point_alt = geojson.json()["geometry"]["coordinates"][0][2]
    assert first_point_alt == 2000.0  # the map/barogram also reflect the calibrated value

    observation = db_session.query(SiteObservation).filter_by(kind="takeoff").one()
    assert observation.alt_m == 1900.0  # the RAW reading, never the calibrated one


async def test_reupload_identical_file_is_a_noop(client, make_token, base_entities, flight):
    headers = make_token(user=base_entities[0])
    first = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    second = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_upload_different_file_replaces_track(client, make_token, base_entities, flight):
    headers = make_token(user=base_entities[0])
    first = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    second = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("no_baro_flight.igc", NO_BARO_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] != first.json()["id"]
    assert second.json()["alt_source"] == "GNSS"


async def test_upload_corrupt_file_is_rejected(client, make_token, base_entities, flight):
    headers = make_token(user=base_entities[0])
    resp = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("corrupt.igc", CORRUPT_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_FAILED"

    missing = await client.get(f"/api/flights/{flight.id}/igc", headers=headers)
    assert missing.status_code == 404


async def test_get_igc_without_a_track_is_404(client, make_token, base_entities, flight):
    headers = make_token(user=base_entities[0])
    resp = await client.get(f"/api/flights/{flight.id}/igc", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ENTITY_NOT_FOUND"


async def test_detach_removes_track(client, make_token, base_entities, flight):
    headers = make_token(user=base_entities[0])
    await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    deleted = await client.delete(f"/api/flights/{flight.id}/igc", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/flights/{flight.id}/igc", headers=headers)
    assert missing.status_code == 404


async def test_upload_writes_back_takeoff_and_landing_time_detach_clears_them(
    client, make_token, base_entities, flight, db_session
):
    headers = make_token(user=base_entities[0])
    await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    db_session.refresh(flight)
    assert flight.takeoff_time is not None
    assert flight.landing_time is not None
    assert flight.landing_time > flight.takeoff_time

    await client.delete(f"/api/flights/{flight.id}/igc", headers=headers)
    db_session.refresh(flight)
    assert flight.takeoff_time is None
    assert flight.landing_time is None


async def test_upload_file_already_attached_to_another_flight_is_409_not_500(
    client, make_token, base_entities, flight, db_session
):
    """uq_igc_tracks_owner_sha256 is per-owner: the same physical recording can only be
    attached to one flight at a time. A second flight — even one whose own earlier
    (different) track was already detached — must get a clear 409 CONFLICT, not an
    unhandled IntegrityError surfacing as a 500."""
    from flightlog.database.models import Flight

    user = base_entities[0]
    other_flight = Flight(
        owner_id=user.id,
        flight_date=flight.flight_date,
        launch_site_id=flight.launch_site_id,
        landing_site_id=flight.landing_site_id,
        category_id=flight.category_id,
    )
    db_session.add(other_flight)
    db_session.commit()

    headers = make_token(user=user)

    # `flight` ends up holding valid_flight.igc (still attached).
    resp = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200

    # `other_flight` had a different (wrong) file uploaded, then detached.
    wrong = await client.post(
        f"/api/flights/{other_flight.id}/igc",
        files={"file": ("no_baro_flight.igc", NO_BARO_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert wrong.status_code == 200
    detach = await client.delete(f"/api/flights/{other_flight.id}/igc", headers=headers)
    assert detach.status_code == 204

    # Uploading the file already attached to `flight` onto `other_flight` must not 500.
    conflict = await client.post(
        f"/api/flights/{other_flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"]["flight_id"] == flight.id

    # `other_flight` must still have no track attached (the failed attempt is not
    # half-applied).
    missing = await client.get(f"/api/flights/{other_flight.id}/igc", headers=headers)
    assert missing.status_code == 404


async def test_another_users_flight_is_404_not_403(
    client, make_token, base_entities, flight, make_user
):
    other = make_user(email="other@example.com")
    headers = make_token(user=other)
    resp = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid_flight.igc", VALID_IGC, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 404
