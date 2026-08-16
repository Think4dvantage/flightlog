"""
API key minting/verification (service-level) and the pilot-facing `/api/keys` CRUD surface
(HTTP-level). The API-key-*authenticated* integration surface itself is covered separately in
test_integration_v1.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from flightlog.services.apikeys import mint_key, verify_key

# ---- service-level ----


def test_mint_and_verify_round_trip():
    minted = mint_key()
    assert minted.plaintext.startswith("flg_")
    assert verify_key(minted.plaintext, minted.key_hash)


def test_tampered_key_fails_verification():
    minted = mint_key()
    tampered = minted.plaintext[:-1] + ("a" if minted.plaintext[-1] != "a" else "b")
    assert not verify_key(tampered, minted.key_hash)


def test_malformed_key_fails_verification():
    minted = mint_key()
    assert not verify_key("not-a-real-key", minted.key_hash)


# ---- HTTP-level: /api/keys ----


@pytest.fixture
def owner(make_user):
    return make_user()


async def test_create_key_shows_plaintext_once(client, make_token, owner):
    headers = make_token(user=owner)
    res = await client.post(
        "/api/keys",
        json={"name": "VidFactory", "scopes": ["flights:read"]},
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["key"].startswith("flg_")
    assert "key_hash" not in body


async def test_list_keys_never_shows_the_plaintext(client, make_token, owner):
    headers = make_token(user=owner)
    await client.post(
        "/api/keys", json={"name": "VidFactory", "scopes": ["flights:read"]}, headers=headers
    )
    res = await client.get("/api/keys", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert "key" not in body[0]
    assert "key_hash" not in body[0]
    assert body[0]["key_prefix"]


async def test_expiry_round_trips_in_create_and_list_responses(client, make_token, owner):
    headers = make_token(user=owner)
    expires_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    created = await client.post(
        "/api/keys",
        json={"name": "VidFactory", "scopes": ["flights:read"], "expires_at": expires_at},
        headers=headers,
    )
    assert created.status_code == 201
    created_expiry = datetime.fromisoformat(created.json()["expires_at"])
    assert abs((created_expiry - datetime.fromisoformat(expires_at)).total_seconds()) < 1

    listed = await client.get("/api/keys", headers=headers)
    listed_expiry = datetime.fromisoformat(listed.json()[0]["expires_at"])
    assert listed_expiry == created_expiry


async def test_unknown_scope_is_rejected(client, make_token, owner):
    headers = make_token(user=owner)
    res = await client.post(
        "/api/keys", json={"name": "bad", "scopes": ["not:a:scope"]}, headers=headers
    )
    assert res.status_code == 422


async def test_revoke_takes_effect_immediately(client, make_token, owner):
    headers = make_token(user=owner)
    created = await client.post(
        "/api/keys", json={"name": "VidFactory", "scopes": ["flights:read"]}, headers=headers
    )
    key_id = created.json()["id"]
    plaintext = created.json()["key"]

    ok = await client.get(
        "/api/integration/v1/flights/does-not-exist", headers={"X-API-Key": plaintext}
    )
    assert ok.status_code == 404  # authenticated fine, just no such flight

    revoked = await client.post(f"/api/keys/{key_id}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    rejected = await client.get(
        "/api/integration/v1/flights/does-not-exist", headers={"X-API-Key": plaintext}
    )
    assert rejected.status_code == 401


async def test_expired_key_is_rejected(client, make_token, owner, db_session):
    from flightlog.database.models import ApiKey

    headers = make_token(user=owner)
    created = await client.post(
        "/api/keys", json={"name": "VidFactory", "scopes": ["flights:read"]}, headers=headers
    )
    key_id = created.json()["id"]
    plaintext = created.json()["key"]

    row = db_session.get(ApiKey, key_id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    res = await client.get(
        "/api/integration/v1/flights/does-not-exist", headers={"X-API-Key": plaintext}
    )
    assert res.status_code == 401


async def test_revoked_key_stays_rejected_even_before_its_expiry(
    client, make_token, owner, db_session
):
    """revoked_at always wins over expires_at — no scenario where a revoked-but-not-yet-
    expired key still works."""
    from flightlog.database.models import ApiKey

    headers = make_token(user=owner)
    created = await client.post(
        "/api/keys",
        json={
            "name": "VidFactory",
            "scopes": ["flights:read"],
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
        headers=headers,
    )
    key_id = created.json()["id"]
    plaintext = created.json()["key"]

    row = db_session.get(ApiKey, key_id)
    from flightlog.database.models import utcnow

    row.revoked_at = utcnow()
    db_session.commit()

    res = await client.get(
        "/api/integration/v1/flights/does-not-exist", headers={"X-API-Key": plaintext}
    )
    assert res.status_code == 401


async def test_missing_api_key_is_rejected(client):
    res = await client.get("/api/integration/v1/flights/does-not-exist")
    assert res.status_code == 401


async def test_cross_owner_key_management_is_404_not_403(client, make_token, make_user):
    owner_a = make_user(email="a@example.com")
    owner_b = make_user(email="b@example.com")
    created = await client.post(
        "/api/keys",
        json={"name": "mine", "scopes": ["flights:read"]},
        headers=make_token(user=owner_a),
    )
    key_id = created.json()["id"]

    res = await client.post(f"/api/keys/{key_id}/revoke", headers=make_token(user=owner_b))
    assert res.status_code == 404


async def test_delete_requires_revoke_first(client, make_token, owner):
    headers = make_token(user=owner)
    created = await client.post(
        "/api/keys", json={"name": "VidFactory", "scopes": ["flights:read"]}, headers=headers
    )
    key_id = created.json()["id"]

    still_live = await client.delete(f"/api/keys/{key_id}", headers=headers)
    assert still_live.status_code == 409

    await client.post(f"/api/keys/{key_id}/revoke", headers=headers)
    deleted = await client.delete(f"/api/keys/{key_id}", headers=headers)
    assert deleted.status_code == 204
