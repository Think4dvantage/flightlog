"""GET /api/import-report — frozen, read-only historical import findings."""

from __future__ import annotations

from flightlog.core.import_history import HISTORICAL_IMPORT_SUMMARY


async def test_import_report_requires_auth(client):
    resp = await client.get("/api/import-report")
    assert resp.status_code == 401


async def test_import_report_matches_frozen_constant(client, make_token):
    headers = make_token()
    resp = await client.get("/api/import-report", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["imported_at"] == HISTORICAL_IMPORT_SUMMARY.imported_at
    assert body["flights_written"] == HISTORICAL_IMPORT_SUMMARY.flights_written == 600

    assert len(body["unresolved_gear"]) == 1
    assert body["unresolved_gear"][0] == {
        "kind": "harness",
        "value": "Advance Success 2",
        "flight_count": 3,
    }

    assert len(body["region_mismatches"]) == 3
    assert {"region": "Interlaken", "computed": 400, "sheet": 397} in body["region_mismatches"]

    assert body["altgain_mismatches"] == [
        {"row": 387, "computed_alt_gain_m": 0, "sheet_altgain": 350, "delta": -350}
    ]

    assert len(body["buddy_proposals"]) == 7
    assert {"name": "Tom", "flight_count": 134} in body["buddy_proposals"]
