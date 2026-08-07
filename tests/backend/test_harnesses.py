"""Harnesses CRUD, retire, ownership scoping, and delete-blocked-while-referenced."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def other_user_flight_setup(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Harness, Site

    owner = make_user(email="owner@example.com")
    harness = Harness(owner_id=owner.id, brand="Advance", model="Success")
    site = Site(owner_id=owner.id, name="Launch", is_launch=True)
    category = FlightCategory(owner_id=owner.id, name="Cat", slug="cat")
    db_session.add_all([harness, site, category])
    db_session.commit()

    flight = Flight(
        owner_id=owner.id,
        flight_date=date(2020, 1, 1),
        launch_site_id=site.id,
        category_id=category.id,
        harness_id=harness.id,
    )
    db_session.add(flight)
    db_session.commit()
    return owner, harness


async def test_create_and_list_harness(client, make_token):
    headers = make_token()
    resp = await client.post(
        "/api/harnesses", json={"brand": "Advance", "model": "Success 2"}, headers=headers
    )
    assert resp.status_code == 201

    listed = await client.get("/api/harnesses", headers=headers)
    assert len(listed.json()) == 1


async def test_retire_hides_from_default_list(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/harnesses", json={"brand": "Advance", "model": "Success"}, headers=headers
    )
    harness_id = created.json()["id"]

    retired = await client.post(f"/api/harnesses/{harness_id}/retire", headers=headers)
    assert retired.json()["retired_at"] is not None

    default_list = await client.get("/api/harnesses", headers=headers)
    assert default_list.json() == []


async def test_get_update_delete_own_harness(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/harnesses", json={"brand": "Advance", "model": "Success"}, headers=headers
    )
    harness_id = created.json()["id"]

    updated = await client.put(
        f"/api/harnesses/{harness_id}", json={"harness_type": "reversible"}, headers=headers
    )
    assert updated.json()["harness_type"] == "reversible"

    deleted = await client.delete(f"/api/harnesses/{harness_id}", headers=headers)
    assert deleted.status_code == 204


async def test_delete_blocked_while_referenced_by_a_flight(
    client, make_token, other_user_flight_setup
):
    owner, harness = other_user_flight_setup
    headers = make_token(user=owner)

    resp = await client.delete(f"/api/harnesses/{harness.id}", headers=headers)
    assert resp.status_code == 409


async def test_another_users_harness_is_404_not_403(client, make_token, other_user_flight_setup):
    _owner, harness = other_user_flight_setup
    other_headers = make_token(email="intruder@example.com")

    for method, path in [
        ("get", f"/api/harnesses/{harness.id}"),
        ("put", f"/api/harnesses/{harness.id}"),
        ("delete", f"/api/harnesses/{harness.id}"),
        ("post", f"/api/harnesses/{harness.id}/retire"),
    ]:
        resp = await client.request(method, path, headers=other_headers, json={"brand": "x"})
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, make_user):
    victim = make_user(email="victim@example.com")
    headers = make_token()

    resp = await client.post(
        "/api/harnesses",
        json={"brand": "Advance", "model": "Success", "owner_id": victim.id},
        headers=headers,
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id
