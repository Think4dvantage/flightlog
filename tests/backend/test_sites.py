"""Sites CRUD, per-pilot prefs, ownership scoping, and delete-blocked-while-referenced."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def other_user_flight_setup(db_session, make_user):
    """A second user's site referenced by one of their flights — for cross-owner and
    delete-blocked assertions."""
    from flightlog.database.models import Flight, FlightCategory, Site

    owner = make_user(email="owner@example.com")
    site = Site(owner_id=owner.id, name="Owned Site", is_launch=True, elevation_m=1000)
    category = FlightCategory(owner_id=owner.id, name="Cat", slug="cat")
    db_session.add_all([site, category])
    db_session.commit()

    flight = Flight(
        owner_id=owner.id,
        flight_date=date(2020, 1, 1),
        launch_site_id=site.id,
        category_id=category.id,
    )
    db_session.add(flight)
    db_session.commit()
    return owner, site


async def test_create_and_list_site(client, make_token):
    headers = make_token()
    resp = await client.post(
        "/api/sites",
        json={"name": "Hohwald", "is_launch": True, "elevation_m": 1580},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Hohwald"
    assert body["owner_id"] is not None

    listed = await client.get("/api/sites", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_site_must_be_launch_or_landing(client, make_token):
    headers = make_token()
    resp = await client.post("/api/sites", json={"name": "Neither"}, headers=headers)
    assert resp.status_code == 422


async def test_get_update_delete_own_site(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/sites", json={"name": "Chalet", "is_launch": True}, headers=headers
    )
    site_id = created.json()["id"]

    got = await client.get(f"/api/sites/{site_id}", headers=headers)
    assert got.status_code == 200

    updated = await client.put(f"/api/sites/{site_id}", json={"elevation_m": 1315}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["elevation_m"] == 1315

    deleted = await client.delete(f"/api/sites/{site_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/sites/{site_id}", headers=headers)
    assert gone.status_code == 404


async def test_delete_blocked_while_referenced_by_a_flight(
    client, make_token, other_user_flight_setup
):
    owner, site = other_user_flight_setup
    headers = make_token(user=owner)

    resp = await client.delete(f"/api/sites/{site.id}", headers=headers)
    assert resp.status_code == 409


async def test_another_users_site_is_404_not_403(client, make_token, other_user_flight_setup):
    _owner, site = other_user_flight_setup
    other_headers = make_token(email="intruder@example.com")

    for method, path in [
        ("get", f"/api/sites/{site.id}"),
        ("put", f"/api/sites/{site.id}"),
        ("delete", f"/api/sites/{site.id}"),
    ]:
        resp = await client.request(method, path, headers=other_headers, json={"elevation_m": 1})
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, make_user):
    victim = make_user(email="victim@example.com")
    headers = make_token()

    resp = await client.post(
        "/api/sites",
        json={"name": "Sneaky", "is_launch": True, "owner_id": victim.id},
        headers=headers,
    )
    assert resp.status_code in (201, 422)  # extra field either ignored or rejected, never applied
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id


async def test_site_prefs_upsert(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/sites",
        json={"name": "Bergbo", "is_launch": True, "elevation_m": 1267},
        headers=headers,
    )
    site_id = created.json()["id"]

    resp = await client.put(
        f"/api/sites/{site_id}/prefs",
        json={"alias": "My Bergbo", "elevation_m": 1270, "is_favourite": True},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["alias"] == "My Bergbo"
    assert body["is_favourite"] is True

    # second PUT updates the same row rather than creating a new one
    resp2 = await client.put(
        f"/api/sites/{site_id}/prefs", json={"is_hidden": True}, headers=headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["alias"] == "My Bergbo"  # untouched field survives
    assert resp2.json()["is_hidden"] is True
