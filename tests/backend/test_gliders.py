"""Gliders CRUD, retire, ownership scoping, and delete-blocked-while-referenced."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def other_user_flight_setup(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Glider, Site

    owner = make_user(email="owner@example.com")
    glider = Glider(owner_id=owner.id, brand="Advance", model="Epsilon")
    site = Site(owner_id=owner.id, name="Launch", is_launch=True)
    category = FlightCategory(owner_id=owner.id, name="Cat", slug="cat")
    db_session.add_all([glider, site, category])
    db_session.commit()

    flight = Flight(
        owner_id=owner.id,
        flight_date=date(2020, 1, 1),
        launch_site_id=site.id,
        category_id=category.id,
        glider_id=glider.id,
    )
    db_session.add(flight)
    db_session.commit()
    return owner, glider


async def test_create_and_list_glider(client, make_token):
    headers = make_token()
    resp = await client.post(
        "/api/gliders", json={"brand": "Advance", "model": "Alpha 6", "size": "28"}, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["brand"] == "Advance"

    listed = await client.get("/api/gliders", headers=headers)
    assert len(listed.json()) == 1


async def test_retire_hides_from_default_list(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/gliders", json={"brand": "Advance", "model": "Epsilon"}, headers=headers
    )
    glider_id = created.json()["id"]

    retired = await client.post(f"/api/gliders/{glider_id}/retire", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["retired_at"] is not None

    default_list = await client.get("/api/gliders", headers=headers)
    assert default_list.json() == []

    full_list = await client.get("/api/gliders?include_retired=true", headers=headers)
    assert len(full_list.json()) == 1


async def test_get_update_delete_own_glider(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/gliders", json={"brand": "Advance", "model": "Epsilon"}, headers=headers
    )
    glider_id = created.json()["id"]

    updated = await client.put(
        f"/api/gliders/{glider_id}", json={"nickname": "Ragnar"}, headers=headers
    )
    assert updated.json()["nickname"] == "Ragnar"

    deleted = await client.delete(f"/api/gliders/{glider_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/gliders/{glider_id}", headers=headers)
    assert gone.status_code == 404


async def test_delete_blocked_while_referenced_by_a_flight(
    client, make_token, other_user_flight_setup
):
    owner, glider = other_user_flight_setup
    headers = make_token(user=owner)

    resp = await client.delete(f"/api/gliders/{glider.id}", headers=headers)
    assert resp.status_code == 409


async def test_another_users_glider_is_404_not_403(client, make_token, other_user_flight_setup):
    _owner, glider = other_user_flight_setup
    other_headers = make_token(email="intruder@example.com")

    for method, path in [
        ("get", f"/api/gliders/{glider.id}"),
        ("put", f"/api/gliders/{glider.id}"),
        ("delete", f"/api/gliders/{glider.id}"),
        ("post", f"/api/gliders/{glider.id}/retire"),
    ]:
        resp = await client.request(method, path, headers=other_headers, json={"brand": "x"})
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, make_user):
    victim = make_user(email="victim@example.com")
    headers = make_token()

    resp = await client.post(
        "/api/gliders",
        json={"brand": "Advance", "model": "Epsilon", "owner_id": victim.id},
        headers=headers,
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id
