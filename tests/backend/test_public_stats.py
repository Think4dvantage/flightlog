"""
The public statistics surface (v0.9.5): opt-in gating, full-lifetime-history scope (including
buddy names, confirmed with the pilot), and the personal-bests flight_id nulling for records
whose underlying flight isn't itself public/unlisted.
"""

from __future__ import annotations

import pytest

from flightlog.api.routers.public import limiter
from flightlog.database.models import FlightCategory, Site


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def base_entities(db_session, make_user):
    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True, elevation_m=1500)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True, elevation_m=1000)
    category = FlightCategory(owner_id=user.id, name="Thermal", slug="thermal")
    db_session.add_all([launch, landing, category])
    db_session.commit()
    return user, launch, landing, category


async def _create_flight(client, headers, launch, landing, category, **fields):
    payload = {
        "flight_date": "2020-01-01",
        "launch_site_id": launch.id,
        "landing_site_id": landing.id,
        "category_id": category.id,
        **fields,
    }
    resp = await client.post("/api/flights", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_stats_disabled_by_default(client, make_token, base_entities):
    user, *_ = base_entities
    res = await client.get(f"/api/public/stats/{user.id}")
    assert res.status_code == 404


async def test_disabled_and_nonexistent_stats_404_identically(client, make_user):
    disabled_user = make_user(email="disabled-stats@example.com")
    disabled_res = await client.get(f"/api/public/stats/{disabled_user.id}")
    missing_res = await client.get("/api/public/stats/does-not-exist")

    assert disabled_res.status_code == missing_res.status_code == 404
    assert disabled_res.content == missing_res.content


async def test_enabled_stats_include_full_lifetime_history_and_buddy_names(
    client, make_token, base_entities
):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)

    buddy = await client.post(
        "/api/buddies", json={"display_name": "Tom Realname"}, headers=headers
    )
    assert buddy.status_code == 201
    buddy_id = buddy.json()["id"]

    # A private flight still counts toward the public aggregate totals — the pilot chose
    # entire-lifetime scope, not public-flights-only.
    await _create_flight(
        client, headers, launch, landing, category, duration_min=90, buddy_ids=[buddy_id]
    )

    await client.put("/api/auth/me", json={"public_stats_enabled": True}, headers=headers)

    res = await client.get(f"/api/public/stats/{user.id}")
    assert res.status_code == 200
    body = res.json()

    assert body["owner_display_name"] == user.display_name
    assert body["totals"]["total_flights"] == 1
    assert body["totals"]["total_airtime_min"] == 90

    buddy_rows = body["matrices"]["buddy"]["rows"]
    assert any(row["name"] == "Tom Realname" for row in buddy_rows)

    # Explicit allowlist — nothing private ever appears.
    assert "email" not in body
    assert "hashed_password" not in body


async def test_personal_best_flight_id_nulled_unless_the_flight_is_itself_public(
    client, make_token, base_entities
):
    user, launch, landing, category = base_entities
    headers = make_token(user=user)

    private_id = await _create_flight(client, headers, launch, landing, category, duration_min=300)
    public_id = await _create_flight(client, headers, launch, landing, category, max_alt_m=3000)
    upd = await client.put(
        f"/api/flights/{public_id}", json={"visibility": "public"}, headers=headers
    )
    assert upd.status_code == 200

    await client.put("/api/auth/me", json={"public_stats_enabled": True}, headers=headers)

    res = await client.get(f"/api/public/stats/{user.id}")
    assert res.status_code == 200
    bests = {b["label"]: b for b in res.json()["personal_bests"]}

    assert bests["longest_airtime"]["flight_id"] is None
    assert bests["longest_airtime"]["value"] == 300
    assert bests["max_altitude"]["flight_id"] == public_id
    assert bests["max_altitude"]["value"] == 3000
    # Never a private id, even absent — confirms nulling, not omission of the field.
    assert private_id not in [b["flight_id"] for b in res.json()["personal_bests"]]


async def test_opting_out_removes_public_stats_immediately(client, make_token, base_entities):
    user, *_ = base_entities
    headers = make_token(user=user)
    await client.put("/api/auth/me", json={"public_stats_enabled": True}, headers=headers)
    assert (await client.get(f"/api/public/stats/{user.id}")).status_code == 200

    await client.put("/api/auth/me", json={"public_stats_enabled": False}, headers=headers)
    assert (await client.get(f"/api/public/stats/{user.id}")).status_code == 404


async def test_public_profile_cross_links_to_public_stats(client, make_token, base_entities):
    user, *_ = base_entities
    headers = make_token(user=user)
    await client.put(
        "/api/auth/me",
        json={"public_profile_enabled": True, "public_stats_enabled": True},
        headers=headers,
    )

    res = await client.get(f"/api/public/profiles/{user.id}")
    assert res.status_code == 200
    assert res.json()["public_stats_enabled"] is True


async def test_stats_route_rate_limited(client, make_token, base_entities, patch_config):
    user, *_ = base_entities
    headers = make_token(user=user)
    await client.put("/api/auth/me", json={"public_stats_enabled": True}, headers=headers)

    patch_config.api.public_rate_limit = "2/minute"

    r1 = await client.get(f"/api/public/stats/{user.id}")
    r2 = await client.get(f"/api/public/stats/{user.id}")
    r3 = await client.get(f"/api/public/stats/{user.id}")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "RATE_LIMITED"
