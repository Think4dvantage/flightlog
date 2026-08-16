"""
Starter-category seeding on self-registration (v0.9) — closes the gap `auth.py`'s own
register() comment had reserved since v0.2: a self-registered account previously landed
with zero flight categories and no way to log a flight (category_id is NOT NULL).
"""

from __future__ import annotations

from flightlog.core.user_seed import _STARTER_CATEGORIES, seed_starter_categories
from flightlog.database.models import FlightCategory


async def test_register_seeds_exactly_five_editable_categories(client):
    res = await client.post(
        "/api/auth/register",
        json={
            "email": "newpilot@example.com",
            "display_name": "New Pilot",
            "password": "correct-horse-battery",
        },
    )
    assert res.status_code == 201
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    cats = await client.get("/api/categories", headers=headers)
    assert cats.status_code == 200
    body = cats.json()
    assert len(body) == len(_STARTER_CATEGORIES) == 5
    names = {c["name"] for c in body}
    assert names == {"Thermal", "Soaring", "XC", "Hike&Fly", "Sled run"}

    hike_fly = next(c for c in body if c["name"] == "Hike&Fly")
    assert hike_fly["is_hike_fly"] is True
    assert hike_fly["is_training"] is False

    # Editable afterward, exactly as if the pilot had created it themselves (FR-011).
    renamed = await client.put(
        f"/api/categories/{hike_fly['id']}", json={"name": "H&F"}, headers=headers
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "H&F"


async def test_seed_is_a_no_op_when_already_seeded(db_session, make_user):
    user = make_user()
    seed_starter_categories(db_session, user)
    db_session.commit()
    assert user.seeded_at is not None

    first_seeded_at = user.seeded_at
    seed_starter_categories(db_session, user)  # second call: must not re-seed
    db_session.commit()

    count = db_session.query(FlightCategory).filter(FlightCategory.owner_id == user.id).count()
    assert count == 5
    assert user.seeded_at == first_seeded_at


async def test_seeding_never_runs_for_an_admin_created_account(db_session, make_user):
    """Only the self-registration path seeds — an existing/admin-created account is never
    retroactively touched (spec.md's Acceptance Criteria)."""
    user = make_user()  # make_user never calls seed_starter_categories
    count = db_session.query(FlightCategory).filter(FlightCategory.owner_id == user.id).count()
    assert count == 0
    assert user.seeded_at is None
