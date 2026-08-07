# Feature: Core Data & Excel Import

## Overview
Flightlog v0.1 only holds pilot accounts — there is nowhere yet to record a site, a glider, or a flight.
This feature adds the reference and flight data a pilot actually logs against (sites, gliders, harnesses,
flight categories, flying buddies, flights) with full per-pilot ownership, and moves the pilot's 600
historical flights out of the legacy spreadsheet in one verified, repeatable pass. No page or screen is
built in this feature — it lands the data and the raw access to it that a future screen, or another
service, can build on.

## Clarifications

### Session 2026-08-06
- Q: `features.md`/`RESUME.md` list a site-observations table as in-scope here, but the schema
  reference marks it as arriving alongside flight-track upload, and it has no per-pilot owner — does it
  belong in this feature? → A: No. Deferred to the flight-track feature that actually populates it. The
  drifted docs get corrected as part of this feature's sync, not carried forward.

## User Stories

### P1 — Historical import
As a pilot, I want all 600 of my historical flights, plus my launch/landing sites, gliders, harnesses,
flight categories and flying buddies, moved out of my spreadsheet into the flight log automatically, so
that I have one authoritative record instead of a manually maintained workbook.

**Acceptance Criteria**:
- Running the import against the untouched legacy workbook produces exactly 600 flights.
- Every site, glider, harness and category name that appears in the workbook exists as one canonical
  record afterward — no duplicate records for the same real-world thing because of a spelling variant.
- The import makes no changes to stored data unless explicitly told to write, not merely preview.

### P1 — Trustworthy import report
As a pilot, I want to review exactly what the import did — what was added, what was normalized, what
looked inconsistent — before I trust it, so that a bad import doesn't silently corrupt years of flight
history.

**Acceptance Criteria**:
- The report states, per kind of record, how many source rows were read and how many records were
  written.
- The report lists every value that had to be corrected to match a known site/glider/harness/category,
  and every value that matched nothing and was left for manual review instead of guessed.
- The report states the total flight count per region and flags it if that total does not match the
  spreadsheet's own regional summary, rather than silently trusting either number.
- The report flags any historical flight where today's computed altitude figures would disagree with the
  number the spreadsheet shows for that flight, rather than silently overwriting the discrepancy.

### P1 — Manage my own data
As a pilot, I want to create, view, update and archive my own sites, gliders, harnesses, flight
categories, buddies and flights, so that I can keep my log current going forward without ever reopening
the spreadsheet.

**Acceptance Criteria**:
- Every one of those record kinds can be listed, created, read, updated, and — where retiring rather
  than deleting is the correct action — archived, without needing the spreadsheet.
- A flight category or piece of gear that historical flights still reference cannot be permanently
  removed; it can only be archived, so old flights keep referring to something real.

### P2 — Data stays private per pilot
As a pilot, I want to be certain the system never shows or lets me modify another pilot's data, so that
my flight history stays private even once more pilots join.

**Acceptance Criteria**:
- Attempting to read, edit or delete another pilot's site, glider, harness, category, buddy or flight
  behaves exactly as if that record did not exist.
- Nothing accepted from outside the system can make a new record belong to anyone but the pilot creating
  it.

### P2 — Safe to re-run
As a pilot, I want re-running the import to be safe, so that I can fix a mistake in my spreadsheet and
import again without ending up with duplicate flights.

**Acceptance Criteria**:
- Running the import twice against the same workbook leaves the flight count unchanged after the second
  run.
- A flight already imported is recognized as the same flight even though the source data has no unique
  identifier of its own beyond row order.

### P3 — Buddy suggestions from history
As a pilot, I want the import to notice names of flying buddies mentioned in my old flight notes and
suggest them as contacts, so that I don't have to retype every name I already wrote down once.

**Acceptance Criteria**:
- Names recognized in historical flight notes are presented as proposed contacts.
- No contact is created automatically from a proposal — a proposal only becomes a record when accepted.

## Functional Requirements

- FR-001: The system provides per-pilot create, read, update and archive/delete for launch and landing
  sites. A site may serve as a launch, a landing, or both.
- FR-002: The system maintains one shared list of regions used to group sites; regions are not owned by
  an individual pilot.
- FR-003: The system provides per-pilot create, read, update and retire for gliders (brand, model, size,
  nickname, wing class, whether currently owned, retirement date).
- FR-004: The system provides per-pilot create, read, update and retire for harnesses (brand, model,
  size, type, next reserve-repack date, retirement date).
- FR-005: The system provides per-pilot create, read, update, reorder and archive for flight categories,
  each flaggable as hike-and-fly and/or training.
- FR-006: The system provides per-pilot create, read, update and delete for flying buddies (a display
  name). A buddy can optionally be linked to another pilot's account through a request that either side
  can accept or decline.
- FR-007: Linking a buddy to another pilot's account never reveals whether the target contact info
  belongs to a registered pilot, whether the link succeeds or not.
- FR-008: The system provides per-pilot create, read, update and delete for flights, recording date,
  launch site, landing site, category, glider, harness, duration, participating buddies, and free-text
  notes.
- FR-009: Altitude-derived figures (gain, site height difference, total descent) are computed at read
  time from the relevant site's current elevation, never stored on the flight — so correcting a site's
  elevation retroactively corrects every flight that used it.
- FR-010: A pilot may override a site's elevation for their own use without changing the shared site
  record other pilots see.
- FR-011: A one-shot import reads the legacy workbook and creates records for every entity kind above. It
  runs in preview-only mode by default and only writes when explicitly instructed to.
- FR-012: The import is idempotent: re-running it after the first successful write does not create
  duplicate sites, gliders, harnesses, categories, buddies or flights, even though the source data has no
  native unique identifier for a flight beyond its row position.
- FR-013: The import normalizes known spelling/naming variants in the source data onto one canonical
  record per entity, and reports every normalization it applied.
- FR-014: The import reports every source value it could not confidently match to a known site, glider,
  harness or category, for manual resolution — it never guesses a match silently.
- FR-015: The import recomputes each region's flight count from the imported data and reports any
  mismatch against the spreadsheet's own regional summary, without silently favoring either number.
- FR-016: The import compares its computed altitude-derived figures against the spreadsheet's own
  computed columns for each historical flight and reports mismatches instead of silently overwriting or
  ignoring them.
- FR-017: The import proposes flying-buddy candidates recognized in flight notes without creating them
  automatically.
- FR-018: No pilot can read, modify, or delete another pilot's sites, gliders, harnesses, categories,
  buddies or flights. A record's owner is always determined by who is making the request, never by a
  value supplied in the request itself.

## Success Criteria
- After a full import run, exactly 600 flights exist, matching the legacy workbook's flight count.
- Running the import a second time against the same workbook leaves every count (flights, sites, gliders,
  harnesses, categories, buddies) unchanged from the first run.
- Every historical flight resolves to a valid site and category; any that don't are named individually in
  the import report, not silently dropped.
- The import report accounts for the known 596-vs-600 discrepancy between the workbook's own regional
  summary and its underlying flight rows, rather than reproducing it unexplained.
- A pilot can perform every listed action (create/read/update/archive) on each of their own record kinds,
  and every one of those actions fails cleanly when attempted against another pilot's record.
- Zero historical flights are lost, merged, or duplicated across two consecutive import runs.

## Key Entities

| Entity | Key Attributes | Notes |
|---|---|---|
| Region | name, display order | Shared reference list, not owned by a pilot |
| Site | name, serves-as-launch / serves-as-landing, coordinates, elevation, region, coordinate source | One record can be both a launch and a landing |
| Per-pilot site preference | pilot, site, personal alias, personal elevation override, favourite/hidden flags | Lets a pilot customize a shared site without changing it for others |
| Glider | brand, model, size, nickname, wing class, active/retired | Owned by one pilot |
| Harness | brand, model, size, type, next reserve-repack date, active/retired | Owned by one pilot |
| Flight category | name, hike-and-fly flag, training flag, display order, archived | Owned by one pilot; never hard-deleted once referenced |
| Buddy | display name, linked pilot account (optional), link status | Owned by its creator; linking is a two-sided, privacy-safe request |
| Flight | date, launch site, landing site, category, glider, harness, duration, buddies present, notes | Owned by one pilot; altitude figures are computed, not stored |

## Out of Scope
- Uploading, storing or analyzing GPS track files (a later feature).
- Any statistics, rollups or dashboards.
- Any visual screen or page — this feature exposes data access only.
- Importing the secondary workbook sheets (hiking, ground-handling, tandem flights, goals) or the
  external competition-scoring import (a later feature each).
- Sharing flights publicly or with other pilots, and machine/API-key access for other services (later
  features).
- Populating site coordinates or elevation from GPS observations (depends on track upload, out of scope
  here — sites get their elevation from the legacy hand-curated list and, where present, a manually
  dropped map pin).

## Assumptions
- The legacy workbook is present, complete and unmodified at the time the import runs.
- There is exactly one pilot account in the system today, and the import writes every historical record
  against that account.
- The set of regions, and the canonical spelling of each site/glider/harness/category name, can be
  determined from the workbook's own reference sheets plus a maintained list of known misspellings.
- A flight's notes are free text; recognizing a buddy's name in them is a best-effort match, not a
  guarantee — missed or wrongly matched names are corrected by the pilot after the fact, not blocking the
  import.

## Dependencies
- Depends on the pilot account and sign-in capability already shipped.
- Depends on the legacy workbook file being available wherever the import runs.

## Edge Cases
- More than one flight shares the same date (117 known days) — the import must preserve each as a
  distinct flight, using its position in the source data as the tiebreaker, never merging or dropping one.
- The same real-world site, glider, harness or category appears under more than one spelling in the
  source data — it must resolve to a single canonical record, never create a duplicate for a variant
  spelling.
- A flight references a glider, harness or category value that matches nothing known — it is flagged for
  manual review, never silently dropped or force-matched to the nearest guess.
- The import's recomputed region totals don't match the workbook's own summary — both numbers are
  reported; neither is silently treated as correct.
- A historical flight's computed altitude figures disagree with the value the spreadsheet shows for it,
  because the spreadsheet's own formula changed partway through its history — reported as an expected,
  named discrepancy, not treated as an import bug.
- A pilot tries to archive a flight category, glider or harness that current or historical flights still
  reference — the record is archived (hidden from future selection) but never deleted, and existing
  flights keep referencing it unchanged.
- A pilot tries to link a buddy to an email address that isn't a registered pilot — the request behaves
  identically to linking a valid but not-yet-accepted address, revealing nothing about whether the
  address is registered.
