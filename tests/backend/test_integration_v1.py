"""
`/api/integration/v1` — the API-key-authenticated surface an external tool (VidFactory)
reads. `/api/keys` itself (JWT-authenticated key management) is covered in test_api_keys.py;
this file assumes a minted key and exercises the machine-facing surface it unlocks.
"""

from __future__ import annotations

import pytest

from flightlog.database.models import FlightCategory, IgcSegment, IgcTrack, Site, utcnow


@pytest.fixture
def flight_setup(db_session, make_user):
    """A pilot with one flight, ready to key-scope requests against."""
    from datetime import date

    from flightlog.database.models import Flight

    user = make_user()
    launch = Site(owner_id=user.id, name="Beatenberg", is_launch=True, elevation_m=1500)
    landing = Site(owner_id=user.id, name="Interlaken", is_landing=True, elevation_m=560)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, landing, category])
    db_session.commit()

    flight = Flight(
        owner_id=user.id,
        flight_date=date(2026, 6, 1),
        launch_site_id=launch.id,
        landing_site_id=landing.id,
        category_id=category.id,
        max_alt_m=2200,
    )
    db_session.add(flight)
    db_session.commit()
    return user, flight


async def _mint(client, headers, scopes):
    res = await client.post(
        "/api/keys", json={"name": "VidFactory", "scopes": scopes}, headers=headers
    )
    return res.json()["key"]


async def test_correctly_scoped_key_reads_owned_flight(client, make_token, flight_setup):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flights:read"])

    res = await client.get(
        f"/api/integration/v1/flights/{flight.id}", headers={"X-API-Key": api_key}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["launch_site_name"] == "Beatenberg"
    assert body["landing_site_name"] == "Interlaken"
    assert body["category_name"] == "Thermikflug"
    assert body["has_igc_track"] is False
    assert body["igc_summary"] is None
    assert body["links"] == []


async def test_wrong_scope_gets_403_not_a_hint(client, make_token, flight_setup):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flight_links:write"])

    res = await client.get(
        f"/api/integration/v1/flights/{flight.id}", headers={"X-API-Key": api_key}
    )
    assert res.status_code == 403


async def test_cross_owner_flight_is_404_not_403(client, make_token, make_user, flight_setup):
    _owner, flight = flight_setup
    other = make_user(email="other@example.com")
    api_key = await _mint(client, make_token(user=other), ["flights:read"])

    res = await client.get(
        f"/api/integration/v1/flights/{flight.id}", headers={"X-API-Key": api_key}
    )
    assert res.status_code == 404


async def test_segments_shape_matches_jwt_gated_equivalent(
    client, make_token, flight_setup, db_session
):
    user, flight = flight_setup
    track = IgcTrack(
        owner_id=user.id,
        flight_id=flight.id,
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
                kind="takeoff",
                start_offset_s=0,
                start_at=utcnow(),
            ),
            IgcSegment(
                track_id=track.id,
                kind="thermal",
                start_offset_s=300,
                start_at=utcnow(),
                duration_s=120,
                alt_change_m=250.0,
                vertical_velocity_ms=2.1,
            ),
            IgcSegment(
                track_id=track.id,
                kind="glide",
                start_offset_s=420,
                start_at=utcnow(),
                duration_s=600,
                alt_change_m=-400.0,
                glide_ratio=6.5,
            ),
            IgcSegment(
                track_id=track.id,
                kind="landing",
                start_offset_s=1200,
                start_at=utcnow(),
            ),
        ]
    )
    db_session.commit()

    owner_headers = make_token(user=user)
    api_key = await _mint(client, owner_headers, ["flights:read"])

    jwt_res = await client.get(f"/api/flights/{flight.id}/igc/segments", headers=owner_headers)
    key_res = await client.get(
        f"/api/integration/v1/flights/{flight.id}/segments", headers={"X-API-Key": api_key}
    )
    assert jwt_res.status_code == key_res.status_code == 200

    jwt_kinds = [s["kind"] for s in jwt_res.json()]
    key_kinds = [s["kind"] for s in key_res.json()]
    assert jwt_kinds == key_kinds == ["takeoff", "thermal", "glide", "landing"]

    thermal = next(s for s in key_res.json() if s["kind"] == "thermal")
    assert thermal["alt_change_m"] == 250.0
    assert thermal["vertical_velocity_ms"] == 2.1
    glide = next(s for s in key_res.json() if s["kind"] == "glide")
    assert glide["alt_change_m"] == -400.0  # a negative alt_change_m glide is the "sink" case

    metadata = await client.get(
        f"/api/integration/v1/flights/{flight.id}", headers={"X-API-Key": api_key}
    )
    assert metadata.json()["has_igc_track"] is True
    assert metadata.json()["igc_summary"] is not None


async def test_segments_404_when_no_track(client, make_token, flight_setup):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flights:read"])
    res = await client.get(
        f"/api/integration/v1/flights/{flight.id}/segments", headers={"X-API-Key": api_key}
    )
    assert res.status_code == 404


async def test_flight_link_push_back_create_then_idempotent_replace(
    client, make_token, flight_setup
):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flight_links:write"])

    created = await client.put(
        f"/api/integration/v1/flights/{flight.id}/links/video/proj-1",
        json={"url": "https://vidfactory.example/proj-1", "label": "Beatenberg highlights"},
        headers={"X-API-Key": api_key},
    )
    assert created.status_code == 200
    assert created.json()["url"] == "https://vidfactory.example/proj-1"

    replaced = await client.put(
        f"/api/integration/v1/flights/{flight.id}/links/video/proj-1",
        json={"url": "https://vidfactory.example/proj-1-v2"},
        headers={"X-API-Key": api_key},
    )
    assert replaced.status_code == 200
    assert replaced.json()["url"] == "https://vidfactory.example/proj-1-v2"
    assert replaced.json()["label"] is None

    owner_headers = make_token(user=user)
    pilot_view = await client.get(f"/api/flights/{flight.id}", headers=owner_headers)
    assert len(pilot_view.json()["links"]) == 1


async def test_flight_link_invalid_url_scheme_rejected(client, make_token, flight_setup):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flight_links:write"])
    res = await client.put(
        f"/api/integration/v1/flights/{flight.id}/links/video/proj-1",
        json={"url": "javascript:alert(1)"},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 422


async def test_flight_link_push_back_requires_write_scope(client, make_token, flight_setup):
    user, flight = flight_setup
    api_key = await _mint(client, make_token(user=user), ["flights:read"])
    res = await client.put(
        f"/api/integration/v1/flights/{flight.id}/links/video/proj-1",
        json={"url": "https://vidfactory.example/proj-1"},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 403


async def test_flight_link_push_back_cross_owner_404(client, make_token, make_user, flight_setup):
    _owner, flight = flight_setup
    other = make_user(email="other@example.com")
    api_key = await _mint(client, make_token(user=other), ["flight_links:write"])
    res = await client.put(
        f"/api/integration/v1/flights/{flight.id}/links/video/proj-1",
        json={"url": "https://vidfactory.example/proj-1"},
        headers={"X-API-Key": api_key},
    )
    assert res.status_code == 404
