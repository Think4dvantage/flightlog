# Data Model: Flight Log UI

## Reused entities — no schema change

This feature is a UI layer over data already modelled and populated as of v0.2. No columns, tables, or
relationships change for `flights`, `sites`, `gliders`, `harnesses`, `flight_categories`, `buddies`,
`flight_buddies`, or `regions` — see `.ai/context/architecture.md` for their full definitions.

One behavioral change, no schema change: `sites.py`'s create/update handlers now set
`coord_source = "manual"` server-side whenever the request includes `lat` and/or `lon` — see
`research.md`. The `coord_source` column already exists (`sites.coord_source`, nullable string); this
feature is the first code path that ever writes `"manual"` into it.

## New: historical import findings (frozen, not a table)

Generated once, from a live dry-run of `run_import()` against `olddata/Flugbuch.xlsx`, and committed as
a Python constant — not a database table (see `research.md` for why). Shape mirrors the fields of
`core/importer.py`'s existing `ImportReport` dataclass that are meaningful to show a pilot after the
fact; fields that only matter mid-import (`rows_read`, per-row skip reasons for rows that in the end
still became flights) are omitted.

```python
# core/import_history.py
from dataclasses import dataclass


@dataclass(frozen=True)
class UnresolvedGearFinding:
    kind: str          # "harness" | "glider"
    value: str          # the raw, unresolved value from the workbook, e.g. "Advance Success 2"
    flight_count: int


@dataclass(frozen=True)
class RegionMismatchFinding:
    region: str
    computed: int        # this project's SITE_REGION-derived count
    sheet: int            # the legacy workbook's Total-column count


@dataclass(frozen=True)
class AltgainMismatchFinding:
    row: int               # 1-based Excel row number, for traceability back to the source
    computed_alt_gain_m: int
    sheet_altgain: int
    delta: int


@dataclass(frozen=True)
class BuddyProposalFinding:
    name: str
    flight_count: int


@dataclass(frozen=True)
class HistoricalImportSummary:
    imported_at: str                                  # ISO date the v0.2 import actually ran
    flights_written: int
    unresolved_gear: tuple[UnresolvedGearFinding, ...]
    region_mismatches: tuple[RegionMismatchFinding, ...]
    altgain_mismatches: tuple[AltgainMismatchFinding, ...]
    buddy_proposals: tuple[BuddyProposalFinding, ...]


HISTORICAL_IMPORT_SUMMARY = HistoricalImportSummary(...)  # populated by re-running the dry-run — see
                                                            # research.md; values are not hand-transcribed
```

### API response schema

```python
# models/import_report.py
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
```

### Validation rules / state transitions

None — this is read-only, immutable reference data with no create/update/delete path. It does not change
in response to any pilot action; the spec's Edge Cases section explicitly accepts that it may go stale
relative to data the pilot has since edited (e.g. a buddy proposal for a name the pilot already added as
a contact under a different spelling).

## Client-side view models (frontend only, not persisted)

Not a database concern, but worth stating since several pages join data that lives in separate API
responses:

- **Flights list row** = a `FlightOut` joined against cached `sites` (for launch/landing names),
  `flight_categories`, `gliders`, `harnesses`, and `buddies` lists, fetched once per page load.
- **Flight detail** = the same join, applied to a single `FlightOut`.
- **Site map marker** = a `SiteOut` with non-null `lat`/`lon`; sites without coordinates are listed but
  not plotted.

These joins happen in browser memory and are never sent back to the server.
