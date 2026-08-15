"""Goals: import from the real Ziele sheet, then full CRUD, status filter, mark-done."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from flightlog.core.secondary_import import run_secondary_import
from flightlog.database.models import Goal

REAL_WORKBOOK_PATH = Path(__file__).parent.parent.parent / "olddata" / "Flugbuch.xlsx"


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_import_reads_only_the_first_8_columns_and_ignores_the_rest(db_session, make_user):
    """Ziele reports ~505 columns wide per row; every column past the 8th is a formatting
    artifact (research.md) — confirm the importer doesn't choke on that width and produces
    exactly the real row count with sane field values."""
    owner = make_user()
    report = run_secondary_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert report.goals_read == 11
    assert report.goals_written == 11

    goals = db_session.execute(select(Goal)).scalars().all()
    assert len(goals) == 11
    for goal in goals:
        assert goal.title  # every real row has a non-empty Titel
        assert goal.status in ("open", "done")


@pytest.mark.skipif(not REAL_WORKBOOK_PATH.exists(), reason="olddata/Flugbuch.xlsx not present")
def test_import_second_run_is_idempotent(db_session, make_user):
    owner = make_user()
    run_secondary_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)
    second = run_secondary_import(db_session, str(REAL_WORKBOOK_PATH), owner.id, write=True)

    assert second.goals_written == 0
    assert second.goals_skipped_existing == 11
    assert len(db_session.execute(select(Goal)).scalars().all()) == 11


async def test_create_list_get_update_delete_goal(client, make_token):
    headers = make_token()

    created = await client.post(
        "/api/goals",
        json={"title": "Fly the Eiger north face", "difficulty": "schwer"},
        headers=headers,
    )
    assert created.status_code == 201
    goal_id = created.json()["id"]
    assert created.json()["status"] == "open"

    listed = await client.get("/api/goals", headers=headers)
    assert len(listed.json()) == 1

    fetched = await client.get(f"/api/goals/{goal_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Fly the Eiger north face"

    updated = await client.put(
        f"/api/goals/{goal_id}",
        json={"title": "Fly the Eiger north face — winter"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Fly the Eiger north face — winter"

    deleted = await client.delete(f"/api/goals/{goal_id}", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/goals/{goal_id}", headers=headers)
    assert missing.status_code == 404


async def test_status_filter(client, make_token):
    # GoalCreate deliberately has no status field — every goal starts "open" (the DB
    # default); "done" is reached only via the dedicated mark-done action.
    headers = make_token()
    await client.post("/api/goals", json={"title": "Open goal"}, headers=headers)
    done_goal = await client.post("/api/goals", json={"title": "Done goal"}, headers=headers)
    await client.post(f"/api/goals/{done_goal.json()['id']}/mark-done", headers=headers)

    open_only = await client.get("/api/goals?status=open", headers=headers)
    assert [g["title"] for g in open_only.json()] == ["Open goal"]

    done_only = await client.get("/api/goals?status=done", headers=headers)
    assert [g["title"] for g in done_only.json()] == ["Done goal"]


async def test_mark_done(client, make_token):
    headers = make_token()
    created = await client.post("/api/goals", json={"title": "A goal"}, headers=headers)
    goal_id = created.json()["id"]
    assert created.json()["status"] == "open"

    marked = await client.post(f"/api/goals/{goal_id}/mark-done", headers=headers)
    assert marked.status_code == 200
    assert marked.json()["status"] == "done"


async def test_import_key_is_never_accepted_from_the_body(client, make_token):
    headers = make_token()
    created = await client.post(
        "/api/goals", json={"title": "A goal", "import_key": "ziele:999"}, headers=headers
    )
    assert created.status_code == 201
    # import_key isn't even a field on GoalCreate — extra fields are silently dropped by
    # Pydantic's default config, so this just confirms it never reaches the DB unexpectedly.
    assert "import_key" not in created.json()


async def test_another_users_goal_is_404_not_403(client, make_token, make_user):
    owner_headers = make_token()
    created = await client.post("/api/goals", json={"title": "Private goal"}, headers=owner_headers)
    goal_id = created.json()["id"]

    other_headers = make_token(user=make_user(email="other@example.com"))
    resp = await client.get(f"/api/goals/{goal_id}", headers=other_headers)
    assert resp.status_code == 404
