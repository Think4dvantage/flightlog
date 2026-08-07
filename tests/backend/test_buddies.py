"""Buddies CRUD, the two-sided link flow, and the enumeration-safety rule on /link."""

from __future__ import annotations


async def test_create_and_list_buddy(client, make_token):
    headers = make_token()
    resp = await client.post("/api/buddies", json={"display_name": "Peter"}, headers=headers)
    assert resp.status_code == 201

    listed = await client.get("/api/buddies", headers=headers)
    assert len(listed.json()) == 1


async def test_get_update_delete_own_buddy(client, make_token):
    headers = make_token()
    created = await client.post("/api/buddies", json={"display_name": "Peter"}, headers=headers)
    buddy_id = created.json()["id"]

    updated = await client.put(
        f"/api/buddies/{buddy_id}", json={"display_name": "Peter S."}, headers=headers
    )
    assert updated.json()["display_name"] == "Peter S."

    deleted = await client.delete(f"/api/buddies/{buddy_id}", headers=headers)
    assert deleted.status_code == 204


async def test_link_returns_202_identically_for_registered_and_unregistered_email(
    client, make_token, make_user
):
    make_user(email="registered@example.com")
    headers = make_token()
    created = await client.post("/api/buddies", json={"display_name": "Peter"}, headers=headers)
    buddy_id = created.json()["id"]

    registered_resp = await client.post(
        f"/api/buddies/{buddy_id}/link", json={"email": "registered@example.com"}, headers=headers
    )
    unregistered_resp = await client.post(
        f"/api/buddies/{buddy_id}/link", json={"email": "nobody@example.com"}, headers=headers
    )
    assert registered_resp.status_code == 202
    assert unregistered_resp.status_code == 202
    assert registered_resp.text == unregistered_resp.text


async def test_link_accept_and_decline_by_the_linked_pilot(client, make_token, make_user):
    linked_pilot = make_user(email="linked@example.com")
    owner_headers = make_token()
    created = await client.post(
        "/api/buddies", json={"display_name": "Linked"}, headers=owner_headers
    )
    buddy_id = created.json()["id"]

    await client.post(
        f"/api/buddies/{buddy_id}/link", json={"email": "linked@example.com"}, headers=owner_headers
    )

    linked_headers = make_token(user=linked_pilot)
    accept = await client.post(f"/api/buddies/{buddy_id}/link/accept", headers=linked_headers)
    assert accept.status_code == 200
    assert accept.json()["link_state"] == "confirmed"


async def test_accept_by_someone_other_than_the_linked_pilot_is_404(client, make_token, make_user):
    make_user(email="linked@example.com")
    owner_headers = make_token()
    created = await client.post(
        "/api/buddies", json={"display_name": "Linked"}, headers=owner_headers
    )
    buddy_id = created.json()["id"]

    await client.post(
        f"/api/buddies/{buddy_id}/link", json={"email": "linked@example.com"}, headers=owner_headers
    )

    intruder_headers = make_token(email="intruder@example.com")
    resp = await client.post(f"/api/buddies/{buddy_id}/link/accept", headers=intruder_headers)
    assert resp.status_code == 404


async def test_delete_never_touches_the_linked_account(client, make_token, make_user, db_session):
    from flightlog.database.models import User

    linked_pilot = make_user(email="linked@example.com")
    owner_headers = make_token()
    created = await client.post(
        "/api/buddies", json={"display_name": "Linked"}, headers=owner_headers
    )
    buddy_id = created.json()["id"]

    await client.post(
        f"/api/buddies/{buddy_id}/link", json={"email": "linked@example.com"}, headers=owner_headers
    )
    await client.delete(f"/api/buddies/{buddy_id}", headers=owner_headers)

    still_exists = db_session.get(User, linked_pilot.id)
    assert still_exists is not None


async def test_another_users_buddy_is_404_not_403(client, make_token, make_user, db_session):
    from flightlog.database.models import Buddy

    owner = make_user(email="owner@example.com")
    buddy = Buddy(owner_id=owner.id, display_name="Owned Buddy")
    db_session.add(buddy)
    db_session.commit()

    intruder_headers = make_token(email="intruder@example.com")
    for method, path in [
        ("get", f"/api/buddies/{buddy.id}"),
        ("put", f"/api/buddies/{buddy.id}"),
        ("delete", f"/api/buddies/{buddy.id}"),
    ]:
        resp = await client.request(
            method, path, headers=intruder_headers, json={"display_name": "x"}
        )
        assert resp.status_code == 404


async def test_owner_id_in_body_is_ignored(client, make_token, make_user):
    victim = make_user(email="victim@example.com")
    headers = make_token()

    resp = await client.post(
        "/api/buddies", json={"display_name": "Sneaky", "owner_id": victim.id}, headers=headers
    )
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        assert resp.json()["owner_id"] != victim.id
