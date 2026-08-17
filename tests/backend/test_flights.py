"""
Flights CRUD, ownership scoping, and the computed-altitude COALESCE precedence: a flight-level
elevation override beats a user_site_prefs override, which beats the site's own elevation_m.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def base_entities(db_session, make_user):
    """A pilot with a launch site, landing site and category, ready to attach flights to."""
    from flightlog.database.models import FlightCategory, Site

    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True, elevation_m=1500)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True, elevation_m=1000)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, landing, category])
    db_session.commit()
    return user, launch, landing, category


async def test_create_and_list_flight(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)

    resp = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-01",
            "launch_site_id": launch.id,
            "landing_site_id": landing.id,
            "category_id": category.id,
            "max_alt_m": 1700,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["alt_gain_m"] == 200  # 1700 - 1500 (site elevation_m, no overrides)
    assert body["site_drop_m"] == 500  # 1500 - 1000
    assert body["total_descent_m"] == 700  # 1700 - 1000

    listed = await client.get("/api/flights", headers=headers)
    assert len(listed.json()) == 1


async def test_altitude_precedence_flight_override_beats_site_pref_beats_site_default(
    client, make_token, base_entities, db_session
):
    """The COALESCE chain: flight override > user_site_prefs override > sites.elevation_m."""
    from flightlog.database.models import UserSitePref

    user, launch, _landing, category = base_entities
    headers = make_token(user=user)

    # 1. No overrides — falls back to the site's own elevation_m (1500).
    resp1 = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-01",
            "launch_site_id": launch.id,
            "category_id": category.id,
            "max_alt_m": 2000,
        },
        headers=headers,
    )
    assert resp1.json()["alt_gain_m"] == 500  # 2000 - 1500

    # 2. A user_site_prefs override (1600) beats the site default.
    db_session.add(UserSitePref(user_id=user.id, site_id=launch.id, elevation_m=1600))
    db_session.commit()
    resp2 = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-02",
            "launch_site_id": launch.id,
            "category_id": category.id,
            "max_alt_m": 2000,
        },
        headers=headers,
    )
    assert resp2.json()["alt_gain_m"] == 400  # 2000 - 1600

    # 3. A flight-level override (1700) beats the user_site_prefs override.
    resp3 = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-03",
            "launch_site_id": launch.id,
            "category_id": category.id,
            "max_alt_m": 2000,
            "launch_elev_override_m": 1700,
        },
        headers=headers,
    )
    assert resp3.json()["alt_gain_m"] == 300  # 2000 - 1700


async def test_get_update_delete_own_flight(client, make_token, base_entities):
    user, launch, _landing, category = base_entities
    headers = make_token(user=user)
    created = await client.post(
        "/api/flights",
        json={"flight_date": "2020-01-01", "launch_site_id": launch.id, "category_id": category.id},
        headers=headers,
    )
    flight_id = created.json()["id"]

    updated = await client.put(
        f"/api/flights/{flight_id}", json={"duration_min": 45}, headers=headers
    )
    assert updated.json()["duration_min"] == 45

    deleted = await client.delete(f"/api/flights/{flight_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/flights/{flight_id}", headers=headers)
    assert gone.status_code == 404


async def test_nickname_is_optional_and_round_trips(client, make_token, base_entities):
    user, launch, _landing, category = base_entities
    headers = make_token(user=user)

    created = await client.post(
        "/api/flights",
        json={"flight_date": "2020-01-01", "launch_site_id": launch.id, "category_id": category.id},
        headers=headers,
    )
    assert created.json()["nickname"] is None

    flight_id = created.json()["id"]
    updated = await client.put(
        f"/api/flights/{flight_id}", json={"nickname": "Bruchlandung special"}, headers=headers
    )
    assert updated.json()["nickname"] == "Bruchlandung special"

    fetched = await client.get(f"/api/flights/{flight_id}", headers=headers)
    assert fetched.json()["nickname"] == "Bruchlandung special"


async def test_has_igc_track_reflects_presence_on_list_and_single_get(
    client, make_token, base_entities, db_session
):
    """List and single-flight GET must agree — the list path batches this, the single path
    queries directly (see api/routers/flights.py's _to_out docstring)."""
    from flightlog.database.models import IgcTrack, utcnow

    user, launch, _landing, category = base_entities
    headers = make_token(user=user)

    with_track = await client.post(
        "/api/flights",
        json={"flight_date": "2020-01-01", "launch_site_id": launch.id, "category_id": category.id},
        headers=headers,
    )
    without_track = await client.post(
        "/api/flights",
        json={"flight_date": "2020-01-02", "launch_site_id": launch.id, "category_id": category.id},
        headers=headers,
    )
    with_track_id = with_track.json()["id"]
    without_track_id = without_track.json()["id"]

    assert with_track.json()["has_igc_track"] is False  # not yet uploaded

    db_session.add(
        IgcTrack(
            owner_id=user.id,
            flight_id=with_track_id,
            original_filename="track.igc",
            sha256="a" * 64,
            file_path="irrelevant",
            analyzer_version="test",
            analyzed_at=utcnow(),
        )
    )
    db_session.commit()

    listed = {
        f["id"]: f["has_igc_track"]
        for f in (await client.get("/api/flights", headers=headers)).json()
    }
    assert listed[with_track_id] is True
    assert listed[without_track_id] is False

    fetched = await client.get(f"/api/flights/{with_track_id}", headers=headers)
    assert fetched.json()["has_igc_track"] is True


async def test_another_users_flight_is_404_not_403(client, make_token, base_entities):
    user, launch, _landing, category = base_entities
    owner_headers = make_token(user=user)
    created = await client.post(
        "/api/flights",
        json={"flight_date": "2020-01-01", "launch_site_id": launch.id, "category_id": category.id},
        headers=owner_headers,
    )
    flight_id = created.json()["id"]

    intruder_headers = make_token(email="intruder@example.com")
    for method, path in [
        ("get", f"/api/flights/{flight_id}"),
        ("put", f"/api/flights/{flight_id}"),
        ("delete", f"/api/flights/{flight_id}"),
    ]:
        resp = await client.request(
            method, path, headers=intruder_headers, json={"duration_min": 1}
        )
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, base_entities, make_user):
    user, launch, _landing, category = base_entities
    victim = make_user(email="victim@example.com")
    headers = make_token(user=user)

    resp = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-01",
            "launch_site_id": launch.id,
            "category_id": category.id,
            "owner_id": victim.id,
        },
        headers=headers,
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id


async def test_import_key_is_never_accepted_from_the_body(client, make_token, base_entities):
    user, launch, _landing, category = base_entities
    headers = make_token(user=user)

    resp = await client.post(
        "/api/flights",
        json={
            "flight_date": "2020-01-01",
            "launch_site_id": launch.id,
            "category_id": category.id,
            "import_key": "xlsx:1",
        },
        headers=headers,
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["import_key"] is None
