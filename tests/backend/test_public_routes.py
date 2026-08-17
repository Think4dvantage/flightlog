"""
The unauthenticated public surface (v0.9): per-flight visibility enforcement, the
never-leak-existence 404 shape, public-profile opt-in/opt-out, and rate limiting.
"""

from __future__ import annotations

import pytest

from flightlog.api.routers.public import limiter
from flightlog.database.models import FlightCategory, Site


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    slowapi's Limiter is a module-level singleton (main.py wires `app.state.limiter` to the
    same instance on every create_app() call), so its in-memory counters would otherwise leak
    across tests — a rate-limit test in one test could starve an unrelated test's request in
    another. Reset before and after every test in this file.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def base_entities(db_session, make_user):
    """A pilot with a launch site, landing site and category, ready to attach flights to."""
    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True, elevation_m=1500)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True, elevation_m=1000)
    category = FlightCategory(owner_id=user.id, name="Thermal", slug="thermal")
    db_session.add_all([launch, landing, category])
    db_session.commit()
    return user, launch, landing, category


async def _create_flight(client, headers, launch, landing, category, visibility=None):
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
    flight_id = resp.json()["id"]
    if visibility is not None:
        upd = await client.put(
            f"/api/flights/{flight_id}", json={"visibility": visibility}, headers=headers
        )
        assert upd.status_code == 200
    return flight_id


# ---- flight visibility ----


async def test_flight_defaults_to_private(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category)

    res = await client.get(f"/api/public/flights/{flight_id}")
    assert res.status_code == 404


async def test_public_flight_visible_unauthenticated(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "public")

    res = await client.get(f"/api/public/flights/{flight_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == flight_id
    assert body["launch_site_name"] == "Launch"
    assert body["visibility"] == "public"
    assert body["owner_id"] == user.id
    # Explicit allowlist — nothing private (email, hashed_password, ...) ever appears.
    assert "email" not in body
    assert "hashed_password" not in body


async def test_public_flight_includes_nickname_when_set(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "public")
    upd = await client.put(
        f"/api/flights/{flight_id}",
        json={"nickname": "Bruchlandung special"},
        headers=headers,
    )
    assert upd.status_code == 200

    res = await client.get(f"/api/public/flights/{flight_id}")
    assert res.status_code == 200
    assert res.json()["nickname"] == "Bruchlandung special"


async def test_unlisted_flight_visible_by_direct_url(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "unlisted")

    res = await client.get(f"/api/public/flights/{flight_id}")
    assert res.status_code == 200
    assert res.json()["visibility"] == "unlisted"


async def test_private_flight_and_nonexistent_flight_404_identically(
    client, make_token, base_entities
):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    private_id = await _create_flight(client, headers, launch, landing, category)

    private_res = await client.get(f"/api/public/flights/{private_id}")
    missing_res = await client.get("/api/public/flights/does-not-exist")

    assert private_res.status_code == missing_res.status_code == 404
    # Byte-for-byte, not just structurally equal JSON — plan.md's Risk section requires this
    # exact rigor so a future edit (e.g. adding a header) can't silently make the two
    # distinguishable again without a test catching it.
    assert private_res.content == missing_res.content


async def test_changing_visibility_back_to_private_takes_effect_immediately(
    client, make_token, base_entities
):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "public")

    assert (await client.get(f"/api/public/flights/{flight_id}")).status_code == 200

    await client.put(f"/api/flights/{flight_id}", json={"visibility": "private"}, headers=headers)
    assert (await client.get(f"/api/public/flights/{flight_id}")).status_code == 404


# ---- public profile ----


async def test_profile_disabled_by_default(client, make_token, base_entities):
    user, *_ = base_entities
    res = await client.get(f"/api/public/profiles/{user.id}")
    assert res.status_code == 404


async def test_opted_in_profile_lists_only_public_flights(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    await client.put("/api/auth/me", json={"public_profile_enabled": True}, headers=headers)

    public_id = await _create_flight(client, headers, launch, landing, category, "public")
    await _create_flight(client, headers, launch, landing, category, "unlisted")
    await _create_flight(client, headers, launch, landing, category)  # private

    res = await client.get(f"/api/public/profiles/{user.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == user.display_name
    ids = [f["id"] for f in body["flights"]]
    assert ids == [public_id]


async def test_profile_flight_list_includes_nickname(client, make_token, base_entities):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    await client.put("/api/auth/me", json={"public_profile_enabled": True}, headers=headers)

    public_id = await _create_flight(client, headers, launch, landing, category, "public")
    upd = await client.put(
        f"/api/flights/{public_id}",
        json={"nickname": "Bruchlandung special"},
        headers=headers,
    )
    assert upd.status_code == 200

    res = await client.get(f"/api/public/profiles/{user.id}")
    assert res.status_code == 200
    assert res.json()["flights"][0]["nickname"] == "Bruchlandung special"


async def test_opting_out_removes_profile_immediately(client, make_token, base_entities):
    user, *_ = base_entities
    headers = make_token(user=user)
    await client.put("/api/auth/me", json={"public_profile_enabled": True}, headers=headers)
    assert (await client.get(f"/api/public/profiles/{user.id}")).status_code == 200

    await client.put("/api/auth/me", json={"public_profile_enabled": False}, headers=headers)
    assert (await client.get(f"/api/public/profiles/{user.id}")).status_code == 404


async def test_disabled_and_nonexistent_profile_404_identically(client, make_user):
    disabled_user = make_user(email="disabled@example.com")
    disabled_res = await client.get(f"/api/public/profiles/{disabled_user.id}")
    missing_res = await client.get("/api/public/profiles/does-not-exist")

    assert disabled_res.status_code == missing_res.status_code == 404
    assert disabled_res.content == missing_res.content


# ---- rate limiting ----


async def test_public_route_rate_limited(client, make_token, base_entities, patch_config):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "public")

    patch_config.api.public_rate_limit = "2/minute"

    r1 = await client.get(f"/api/public/flights/{flight_id}")
    r2 = await client.get(f"/api/public/flights/{flight_id}")
    r3 = await client.get(f"/api/public/flights/{flight_id}")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "RATE_LIMITED"


async def test_rate_limit_does_not_affect_authenticated_surface(
    client, make_token, base_entities, patch_config
):
    """The public-surface limiter must never throttle the pilot's own authenticated
    session — FR-008 and spec.md's concurrent-session edge case."""
    user, launch, landing, category = base_entities
    headers = make_token(user=user)
    flight_id = await _create_flight(client, headers, launch, landing, category, "public")

    patch_config.api.public_rate_limit = "1/minute"
    assert (await client.get(f"/api/public/flights/{flight_id}")).status_code == 200
    assert (await client.get(f"/api/public/flights/{flight_id}")).status_code == 429

    # The same client, now with a valid token, hitting an authenticated route: unaffected.
    authed = await client.get(f"/api/flights/{flight_id}", headers=headers)
    assert authed.status_code == 200
