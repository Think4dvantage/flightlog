"""Bulk IGC upload: unambiguous auto-match, same-day ambiguity -> pending, resolve, dismiss."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
VALID = (FIXTURES / "valid_flight.igc").read_bytes()
SAMEDAY_A = (FIXTURES / "sameday_flight_a.igc").read_bytes()
SAMEDAY_B = (FIXTURES / "sameday_flight_b.igc").read_bytes()
CORRUPT = (FIXTURES / "corrupt.igc").read_bytes()


@pytest.fixture
def base_entities(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Site

    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, category])
    db_session.commit()

    # valid_flight.igc is ~602s -> duration_min=10 (600s) is an unambiguous single match.
    flight_auto = Flight(
        owner_id=user.id,
        flight_date=date(2024, 8, 15),
        launch_site_id=launch.id,
        category_id=category.id,
        duration_min=10,
    )
    # Two same-day flights with the same logged duration -> neither is a confident match
    # for a same-day upload (sameday_flight_a/b.igc are both ~602s too).
    flight_same1 = Flight(
        owner_id=user.id,
        flight_date=date(2024, 9, 1),
        launch_site_id=launch.id,
        category_id=category.id,
        duration_min=10,
    )
    flight_same2 = Flight(
        owner_id=user.id,
        flight_date=date(2024, 9, 1),
        launch_site_id=launch.id,
        category_id=category.id,
        duration_min=10,
    )
    db_session.add_all([flight_auto, flight_same1, flight_same2])
    db_session.commit()
    return user, flight_auto, flight_same1, flight_same2


async def test_bulk_upload_auto_matches_flags_ambiguous_and_rejects_invalid(
    client, make_token, base_entities
):
    user, flight_auto, flight_same1, flight_same2 = base_entities
    headers = make_token(user=user)

    resp = await client.post(
        "/api/igc/bulk",
        files=[
            ("files", ("valid.igc", VALID, "application/octet-stream")),
            ("files", ("sameday_a.igc", SAMEDAY_A, "application/octet-stream")),
            ("files", ("corrupt.igc", CORRUPT, "application/octet-stream")),
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    outcomes = {o["filename"]: o for o in resp.json()}

    assert outcomes["valid.igc"]["outcome"] == "auto_attached"
    assert outcomes["valid.igc"]["flight_id"] == flight_auto.id

    assert outcomes["sameday_a.igc"]["outcome"] == "needs_resolution"
    assert set(outcomes["sameday_a.igc"]["candidate_flight_ids"]) == {
        flight_same1.id,
        flight_same2.id,
    }

    assert outcomes["corrupt.igc"]["outcome"] == "rejected"

    attached = await client.get(f"/api/flights/{flight_auto.id}/igc", headers=headers)
    assert attached.status_code == 200

    pending = await client.get("/api/igc/pending", headers=headers)
    assert len(pending.json()) == 1
    pending_id = pending.json()[0]["id"]

    resolved = await client.post(
        f"/api/igc/pending/{pending_id}/resolve",
        json={"flight_id": flight_same1.id},
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["flight_id"] == flight_same1.id

    now_attached = await client.get(f"/api/flights/{flight_same1.id}/igc", headers=headers)
    assert now_attached.status_code == 200

    pending_after = await client.get("/api/igc/pending", headers=headers)
    assert pending_after.json() == []


async def test_reuploading_same_pending_file_is_recognized_not_duplicated(
    client, make_token, base_entities
):
    headers = make_token(user=base_entities[0])
    first = await client.post(
        "/api/igc/bulk",
        files=[("files", ("sameday_b.igc", SAMEDAY_B, "application/octet-stream"))],
        headers=headers,
    )
    second = await client.post(
        "/api/igc/bulk",
        files=[("files", ("sameday_b.igc", SAMEDAY_B, "application/octet-stream"))],
        headers=headers,
    )
    assert first.json()[0]["outcome"] == "needs_resolution"
    assert second.json()[0]["outcome"] == "needs_resolution"
    assert first.json()[0]["pending_id"] == second.json()[0]["pending_id"]

    pending = await client.get("/api/igc/pending", headers=headers)
    assert len(pending.json()) == 1


async def test_pending_can_be_dismissed(client, make_token, base_entities):
    headers = make_token(user=base_entities[0])
    await client.post(
        "/api/igc/bulk",
        files=[("files", ("sameday_b.igc", SAMEDAY_B, "application/octet-stream"))],
        headers=headers,
    )
    pending = (await client.get("/api/igc/pending", headers=headers)).json()
    assert len(pending) == 1

    dismissed = await client.delete(f"/api/igc/pending/{pending[0]['id']}", headers=headers)
    assert dismissed.status_code == 204

    pending_after = (await client.get("/api/igc/pending", headers=headers)).json()
    assert pending_after == []
