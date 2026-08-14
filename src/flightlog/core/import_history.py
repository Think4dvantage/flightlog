"""
Frozen snapshot of the v0.2 production import's findings, for `GET /api/import-report`.

Not a database table — see specs/002-flight-log-ui/research.md for why. The values below were
generated from a live dry-run of `run_import()` against `olddata/Flugbuch.xlsx`
(specs/002-flight-log-ui/data-model.md), not hand-transcribed from RESUME.md; a pure dry-run
never increments `ImportReport.flights_written` (the importer's own `if not write: continue`
skips that line), so `flights_written` here is `rows_read - len(flights_skipped_unresolved)` —
the count that would be written, with zero unresolved rows in this workbook.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnresolvedGearFinding:
    kind: str  # "harness" | "glider"
    value: str
    flight_count: int


@dataclass(frozen=True)
class RegionMismatchFinding:
    region: str
    computed: int
    sheet: int


@dataclass(frozen=True)
class AltgainMismatchFinding:
    row: int
    computed_alt_gain_m: int
    sheet_altgain: int
    delta: int


@dataclass(frozen=True)
class BuddyProposalFinding:
    name: str
    flight_count: int


@dataclass(frozen=True)
class HistoricalImportSummary:
    imported_at: str
    flights_written: int
    unresolved_gear: tuple[UnresolvedGearFinding, ...]
    region_mismatches: tuple[RegionMismatchFinding, ...]
    altgain_mismatches: tuple[AltgainMismatchFinding, ...]
    buddy_proposals: tuple[BuddyProposalFinding, ...]


HISTORICAL_IMPORT_SUMMARY = HistoricalImportSummary(
    imported_at="2026-08-07",
    flights_written=600,
    unresolved_gear=(
        UnresolvedGearFinding(kind="harness", value="Advance Success 2", flight_count=3),
    ),
    region_mismatches=(
        RegionMismatchFinding(region="Fiesch", computed=0, sheet=1),
        RegionMismatchFinding(region="Interlaken", computed=400, sheet=397),
        RegionMismatchFinding(region="Grindelwald", computed=34, sheet=33),
    ),
    altgain_mismatches=(
        AltgainMismatchFinding(row=387, computed_alt_gain_m=0, sheet_altgain=350, delta=-350),
    ),
    buddy_proposals=(
        BuddyProposalFinding(name="Jürg", flight_count=3),
        BuddyProposalFinding(name="Beni", flight_count=2),
        BuddyProposalFinding(name="Susi", flight_count=24),
        BuddyProposalFinding(name="Tigi", flight_count=12),
        BuddyProposalFinding(name="Tom", flight_count=134),
        BuddyProposalFinding(name="Ueli", flight_count=61),
        BuddyProposalFinding(name="Simon", flight_count=16),
    ),
)
