"""Pydantic response schema for GET /api/import-report. Read-only — no create/update/delete."""

from __future__ import annotations

from pydantic import BaseModel


class UnresolvedGearOut(BaseModel):
    kind: str
    value: str
    flight_count: int


class RegionMismatchOut(BaseModel):
    region: str
    computed: int
    sheet: int


class AltgainMismatchOut(BaseModel):
    row: int
    computed_alt_gain_m: int
    sheet_altgain: int
    delta: int


class BuddyProposalOut(BaseModel):
    name: str
    flight_count: int


class HistoricalImportReportOut(BaseModel):
    imported_at: str
    flights_written: int
    unresolved_gear: list[UnresolvedGearOut]
    region_mismatches: list[RegionMismatchOut]
    altgain_mismatches: list[AltgainMismatchOut]
    buddy_proposals: list[BuddyProposalOut]
