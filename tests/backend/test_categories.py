"""
Categories CRUD, reorder, archive, ownership scoping, delete-blocked-while-referenced, and the
route-order regression: PUT /reorder must never be swallowed by PUT /{id}.
"""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def other_user_flight_setup(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Site

    owner = make_user(email="owner@example.com")
    category = FlightCategory(owner_id=owner.id, name="Thermikflug", slug="thermikflug")
    site = Site(owner_id=owner.id, name="Launch", is_launch=True)
    db_session.add_all([category, site])
    db_session.commit()

    flight = Flight(
        owner_id=owner.id,
        flight_date=date(2020, 1, 1),
        launch_site_id=site.id,
        category_id=category.id,
    )
    db_session.add(flight)
    db_session.commit()
    return owner, category


async def test_create_and_list_category(client, make_token):
    headers = make_token()
    resp = await client.post(
        "/api/categories", json={"name": "Hike&Fly", "is_hike_fly": True}, headers=headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "hike-fly"
    assert body["is_hike_fly"] is True

    listed = await client.get("/api/categories", headers=headers)
    assert len(listed.json()) == 1


async def test_reorder_is_not_swallowed_by_id_route(client, make_token):
    """Regression: PUT /api/categories/reorder must resolve to the reorder handler, not the
    {category_id} handler with category_id='reorder'."""
    headers = make_token()
    a = (await client.post("/api/categories", json={"name": "A"}, headers=headers)).json()
    b = (await client.post("/api/categories", json={"name": "B"}, headers=headers)).json()

    resp = await client.put(
        "/api/categories/reorder", json={"ids": [b["id"], a["id"]]}, headers=headers
    )
    assert resp.status_code == 200
    ordered = resp.json()
    assert [c["id"] for c in ordered] == [b["id"], a["id"]]
    assert ordered[0]["sort_order"] == 0
    assert ordered[1]["sort_order"] == 1


async def test_archive_hides_from_default_list_but_survives(client, make_token):
    headers = make_token()
    created = await client.post("/api/categories", json={"name": "Prüfung"}, headers=headers)
    category_id = created.json()["id"]

    archived = await client.post(f"/api/categories/{category_id}/archive", headers=headers)
    assert archived.json()["archived_at"] is not None

    default_list = await client.get("/api/categories", headers=headers)
    assert default_list.json() == []

    full_list = await client.get("/api/categories?include_archived=true", headers=headers)
    assert len(full_list.json()) == 1


async def test_delete_blocked_while_referenced_by_a_flight(
    client, make_token, other_user_flight_setup
):
    owner, category = other_user_flight_setup
    headers = make_token(user=owner)

    resp = await client.delete(f"/api/categories/{category.id}", headers=headers)
    assert resp.status_code == 409


async def test_another_users_category_is_404_not_403(client, make_token, other_user_flight_setup):
    _owner, category = other_user_flight_setup
    other_headers = make_token(email="intruder@example.com")

    for method, path in [
        ("get", f"/api/categories/{category.id}"),
        ("put", f"/api/categories/{category.id}"),
        ("delete", f"/api/categories/{category.id}"),
        ("post", f"/api/categories/{category.id}/archive"),
    ]:
        resp = await client.request(method, path, headers=other_headers, json={"name": "x"})
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, make_user):
    victim = make_user(email="victim@example.com")
    headers = make_token()

    resp = await client.post(
        "/api/categories", json={"name": "Sneaky", "owner_id": victim.id}, headers=headers
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id
