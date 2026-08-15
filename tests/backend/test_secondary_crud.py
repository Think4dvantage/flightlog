"""
Full CRUD for hikes, groundhandling sessions, and tandem flights — added post-ship (v0.7.x)
per direct pilot feedback ("I can't add new ones"). Import-time creation (core/secondary_import.py)
is covered separately in test_secondary_import.py; this file covers the pilot-facing CRUD surface.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def owner(make_user):
    return make_user()


# ---- hikes ----


async def test_hike_create_get_update_delete(client, make_token, owner):
    headers = make_token(user=owner)

    created = await client.post(
        "/api/hikes",
        json={
            "hike_date": "2024-06-01",
            "start_place": "Talstation",
            "destination_place": "Gipfel",
            "ascent_m": 800,
            "duration_min": 120,
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["start_place"] == "Talstation"
    assert body["flight_id"] is None
    hike_id = body["id"]

    fetched = await client.get(f"/api/hikes/{hike_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["ascent_m"] == 800

    updated = await client.put(f"/api/hikes/{hike_id}", json={"ascent_m": 900}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["ascent_m"] == 900

    deleted = await client.delete(f"/api/hikes/{hike_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/hikes/{hike_id}", headers=headers)
    assert gone.status_code == 404


async def test_hike_can_be_linked_to_a_flight_manually(client, make_token, owner, db_session):
    from datetime import date

    from flightlog.database.models import Flight, FlightCategory, Site

    headers = make_token(user=owner)
    site = Site(owner_id=owner.id, name="Launch", is_launch=True)
    category = FlightCategory(owner_id=owner.id, name="Hike&Fly", slug="hike-fly", is_hike_fly=True)
    db_session.add_all([site, category])
    db_session.commit()
    flight = Flight(
        owner_id=owner.id,
        flight_date=date(2024, 6, 1),
        launch_site_id=site.id,
        category_id=category.id,
    )
    db_session.add(flight)
    db_session.commit()

    created = await client.post(
        "/api/hikes",
        json={
            "hike_date": "2024-06-01",
            "start_place": "Talstation",
            "destination_place": "Gipfel",
            "flight_id": flight.id,
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["flight_id"] == flight.id


async def test_hike_import_key_never_accepted_from_body(client, make_token, owner):
    headers = make_token(user=owner)
    resp = await client.post(
        "/api/hikes",
        json={
            "hike_date": "2024-06-01",
            "start_place": "A",
            "destination_place": "B",
            "import_key": "fitnessprogramm:1",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["id"] is not None
    # import_key silently ignored (not a HikeCreate field) rather than rejected
    assert "import_key" not in resp.json() or resp.json().get("import_key") != "fitnessprogramm:1"


async def test_hike_another_users_row_is_404_not_403(client, make_token, owner, make_user):
    headers = make_token(user=owner)
    created = await client.post(
        "/api/hikes",
        json={"hike_date": "2024-06-01", "start_place": "A", "destination_place": "B"},
        headers=headers,
    )
    hike_id = created.json()["id"]

    intruder_headers = make_token(email="intruder@example.com")
    for method, path in [
        ("get", f"/api/hikes/{hike_id}"),
        ("put", f"/api/hikes/{hike_id}"),
        ("delete", f"/api/hikes/{hike_id}"),
    ]:
        resp = await client.request(method, path, headers=intruder_headers, json={"ascent_m": 1})
        assert resp.status_code == 404


# ---- groundhandling sessions ----


async def test_groundhandling_create_get_update_delete(client, make_token, owner):
    headers = make_token(user=owner)

    created = await client.post(
        "/api/groundhandling",
        json={"session_date": "2024-06-01", "place": "Wiese", "duration_min": 45},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    updated = await client.put(
        f"/api/groundhandling/{session_id}", json={"comment": "windy"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["comment"] == "windy"

    deleted = await client.delete(f"/api/groundhandling/{session_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/groundhandling/{session_id}", headers=headers)
    assert gone.status_code == 404


async def test_groundhandling_another_users_row_is_404(client, make_token, owner):
    headers = make_token(user=owner)
    created = await client.post(
        "/api/groundhandling",
        json={"session_date": "2024-06-01", "place": "Wiese"},
        headers=headers,
    )
    session_id = created.json()["id"]

    intruder_headers = make_token(email="intruder@example.com")
    resp = await client.get(f"/api/groundhandling/{session_id}", headers=intruder_headers)
    assert resp.status_code == 404


# ---- tandem flights ----


async def test_tandem_flight_create_get_update_delete(client, make_token, owner):
    headers = make_token(user=owner)

    created = await client.post(
        "/api/tandem-flights",
        json={
            "flight_date": "2024-06-01",
            "launch_place": "Berg",
            "landing_place": "Tal",
            "cost": 0,
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["cost"] == 0  # a free tandem is a real value, not dropped
    tandem_id = body["id"]

    updated = await client.put(
        f"/api/tandem-flights/{tandem_id}", json={"tandem_operator": "AlpineAir"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["tandem_operator"] == "AlpineAir"

    deleted = await client.delete(f"/api/tandem-flights/{tandem_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/tandem-flights/{tandem_id}", headers=headers)
    assert gone.status_code == 404


async def test_tandem_flight_another_users_row_is_404(client, make_token, owner):
    headers = make_token(user=owner)
    created = await client.post(
        "/api/tandem-flights",
        json={"flight_date": "2024-06-01", "launch_place": "Berg", "landing_place": "Tal"},
        headers=headers,
    )
    tandem_id = created.json()["id"]

    intruder_headers = make_token(email="intruder@example.com")
    resp = await client.get(f"/api/tandem-flights/{tandem_id}", headers=intruder_headers)
    assert resp.status_code == 404
