# Feature: Secondary Sheets & XContest Import

## Overview

Retires the last reason to ever reopen `Flugbuch.xlsx`: imports the workbook's four remaining sheets
(hiking/hike-fly, ground-handling practice, tandem flights taken as a passenger, and a personal flying
goals wishlist) into their own tables, and lets the pilot import XContest's official "My Flights" export
to attach an independently-verified XC score/type/URL to flights already in the system. After this
ships, the Excel file has no remaining unique data.

## Clarifications

### Session 2026-08-15
- Q: The real workbook's `Fitnessprogramm` sheet has 85 rows; some rows carry `Airtime`/`Landeplatz`
  values (a hike that became a flight) and some don't (a pure hike). How should an imported hike relate
  to an already-imported `Hike&Fly`-category flight on the same date? → A: Link when unambiguous (one
  hike row and one `Hike&Fly` flight share a date), leave `flight_id` null and report the rest for
  manual linking later — never guessed, mirroring the IGC bulk-match precedent (`architecture.md`).
- Q: XContest's "My Flights" JSON export's exact field names/schema were not found in any public
  documentation this session (the export requires a logged-in XContest session; SkyViz's own
  integration guide describes the *workflow*, not the *schema*). What should the import do? → A: Treat
  the schema as unverified going into planning — `research.md` records this as an explicit open item to
  resolve against one real exported sample file at the start of implementation, the same pattern v0.5
  used for two `libigc` unknowns. The spec below is written at the field-*meaning* level (score, flight
  type, source URL — already the three columns `architecture.md` commits to), not the JSON's literal
  key names, so this remains valid regardless of how that resolves.

## User Stories

### P1 — Must Have

**As a pilot, I want my hiking, ground-handling, and tandem-flight history imported from the old
spreadsheet so none of it is lost when the file stops being opened.**

Acceptance Criteria:
- Every non-empty row in `Fitnessprogramm`, `Groundhandling`, and `Tandemflüge` is imported exactly
  once; running the import again changes nothing (idempotent, matching the existing importer's
  precedent).
- A hike whose date unambiguously matches exactly one already-imported `Hike&Fly`-category flight is
  linked to it; every other hike (no match, or more than one same-day `Hike&Fly` flight) is imported
  unlinked and reported, never guessed.
- Nothing is silently dropped: any row the import cannot fully resolve is still imported with whatever
  it could resolve, and reported — matching the existing importer's "skip and report only the truly
  unresolvable, never guess" rule (FR-014 of `specs/001-core-data-import/spec.md`).

**As a pilot, I want to see my hikes, ground-handling sessions, and tandem flights in the app, listed
separately from my own flights, so my flight log stays about actual flying I did myself.**

Acceptance Criteria:
- Three list views, one per imported type, each showing its own fields (a hike's route/distance/time; a
  ground-handling session's place/duration/comment; a tandem flight's launch/landing/pilot/cost).
- A linked hike's view shows which flight it's linked to, if any.
- None of these three types appear in, or are counted by, the existing `/flights` list or its filters.

### P2 — Should Have

**As a pilot, I want to record and track a personal list of flying goals (site/route ideas I want to
try) so the spreadsheet's wishlist isn't lost and I can keep adding to it going forward.**

Acceptance Criteria:
- Every `Ziele` row is imported: title, wind direction, difficulty level, category, description, links,
  season, status.
- The pilot can create, edit, delete, and mark a goal done going forward — this list is not read-only
  once imported (unlike `/import`'s historical snapshot, which stays frozen).
- Goals are viewable filtered by status (open vs. done) at minimum.

**As a pilot, I want to import my XContest "My Flights" export so my flights show an independently
verified XC score instead of just what I hand-typed.**

Acceptance Criteria:
- The pilot can upload their XContest export and have it matched against already-imported flights.
- An unambiguous match (same date, compatible launch site) attaches the official score, flight type,
  and a link back to the XContest flight page.
- Anything ambiguous, or with no matching flight, is reported for manual resolution, never guessed —
  same rule as every other import path in this app.
- Re-importing the same export changes nothing (idempotent).

### P3 — Nice to Have

**As a pilot, I want the app to show me open goals that match good current conditions (once weather
data exists) so my wishlist becomes actionable, not just a static list.**

Acceptance Criteria: out of scope for this feature (needs `v0.10`'s weather-snapshot work); recorded
here only so the goal-matching intent isn't lost. Not implemented in this feature.

## Functional Requirements

- FR-001: The system MUST import every non-empty row of `Fitnessprogramm`, `Groundhandling`, and
  `Tandemflüge` from the legacy workbook, exactly once, idempotently.
- FR-002: The system MUST attempt to link an imported hike to an already-imported flight only when the
  match (same date, exactly one candidate `Hike&Fly`-category flight) is unambiguous; every other hike
  imports with no link and is reported.
- FR-003: The system MUST provide separate list views for hikes, ground-handling sessions, and tandem
  flights, each showing that type's own fields.
- FR-004: Hikes, ground-handling sessions, and tandem flights MUST NOT appear in, or be counted by, the
  `/flights` list, its filters, or its search.
- FR-005: The system MUST import every `Ziele` row into an editable goals list (not a frozen historical
  snapshot).
- FR-006: The system MUST let the pilot create, edit, delete, and mark a goal done after import.
- FR-007: The system MUST let the pilot filter the goals list by status.
- FR-008: The system MUST let the pilot upload an XContest "My Flights" export and match its entries
  against already-imported flights.
- FR-009: The system MUST attach the official score, flight type, and source URL only to an unambiguous
  match; every other entry (no match or multiple candidates) MUST be reported for manual resolution,
  never guessed.
- FR-010: Re-importing the same XContest export MUST be idempotent — no duplicate attachment, no
  double-counted score.
- FR-011: All user-visible chrome (labels, buttons, navigation, validation messages) MUST go through the
  existing translation mechanism; user-entered data (hike routes, comments, goal titles/descriptions)
  MUST never be translated.
- FR-012: Every view introduced by this feature MUST use the existing dark theme and navigation shell
  consistently with the rest of the application.

## Non-Functional Requirements

- NFR-001: The import of all three secondary sheets together must complete in well under a minute
  against the real workbook (85 + 9 + 17 rows — three orders of magnitude smaller than the 600-flight
  primary import, which already completes quickly).
- NFR-002: Every view introduced by this feature must be usable by keyboard alone, consistent with the
  rest of the application's existing keyboard-navigation standard.
- NFR-003: Deleting a goal, or any bulk action from the XContest import's manual-resolution step, must
  require an explicit confirmation step — none may be a single accidental click.

## Success Criteria

- After this feature ships, `olddata/Flugbuch.xlsx` contains no data not already reproduced somewhere in
  the application — matching `architecture.md`'s "`Flugbuch.xlsx` is retired here" statement for this
  milestone.
- A pilot can find any historical hike, ground-handling session, or tandem flight through its own list
  view without opening the spreadsheet.
- A pilot can see an independently-verified XContest score on a flight without retyping it by hand.
- Nothing imported by this feature is ever silently dropped or silently guessed onto the wrong flight —
  every ambiguity is visible and pilot-resolvable, the same standard the v0.2 and v0.5 imports already
  hold themselves to.

## Key Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| Hike | date, launch place, destination place, ascent/descent (m), distance (km), duration, route description, optional linked flight | `flight_id` nullable per `architecture.md`; a pure hike has no link, a hike that became a flight may |
| Ground-handling session | date, place, duration (min), comment | Matches `architecture.md`'s already-named columns exactly |
| Tandem flight | date, launch site, landing site, tandem pilot/operator (free text), comment, cost | The pilot is the passenger, not the flyer — deliberately not a row in `flights` (`architecture.md`) |
| Goal | title, wind direction, difficulty level, category, description, link(s), target season, status (open/done) | Editable going forward, unlike `/import`'s frozen historical snapshot |
| XContest attachment | which flight, official score, flight type, source URL | Attaches to an existing `flights` row via the three columns `architecture.md` already names (`xc_official_score`/`_type`/`_url`); not a new entity of its own |

## Out of Scope

- Weather-conditions matching against open goals (`v0.10`'s enrichment milestone; P3 story above records
  the intent only).
- Any UI or import path for editing hikes/ground-handling/tandem-flight rows after import beyond what
  FR-006 already covers for goals — the first three types are import-and-view only in this feature,
  matching the spreadsheet's own read-mostly nature for that historical data. (Adding full CRUD for
  historical hikes/tandem-flights, if ever wanted, is a fast-follow, not blocking this milestone.)
- Recomputing or overriding XContest's own score — the imported figure is authoritative and displayed
  as-is (matches the project-wide decision already recorded in `features.md`'s Shelved section against
  in-app XC scoring).
- Any statistics or rollup drawing on this feature's data (hike totals, tandem-flight counts, goal
  completion rate) — that is `v0.7`'s job, not this feature's.

## Assumptions

- There is exactly one pilot account in the system today (matches every prior feature's stated
  assumption).
- The exact JSON schema of an XContest "My Flights" export is not yet known with certainty (see
  Clarifications) — the pilot has, or can obtain, a real sample export to verify the schema against
  before implementation finalizes the parser, the same way `libigc`'s exact API shape was confirmed
  against the installed package rather than guessed.
- A hike-to-flight link is a nice-to-have cross-reference, not something any other feature depends on
  being complete — an unlinked hike is a fully valid, permanent state, not a to-do.

## Dependencies

- Requires the existing `flights` table and `Hike&Fly` category flag (`flight_categories.is_hike_fly`,
  shipped v0.2) for hike-to-flight linking.
- Requires the existing one-shot importer pattern (`core/importer.py`) and its idempotency/reporting
  conventions as the template for this feature's own import paths.
- Requires a real XContest "My Flights" export file to verify the JSON schema against before
  implementation (see Assumptions) — this is a planning-time input, not a runtime dependency.

## Edge Cases

- A `Fitnessprogramm` row with no `Airtime`/`Landeplatz` value: a pure hike, imported with no flight
  link and no attempt to force one.
- Two `Hike&Fly` flights logged on the same date as one hike row: never guessed — the hike imports
  unlinked and is reported as ambiguous, matching FR-002.
- A `Tandemflüge` row with `kosten` (cost) of 0: a real, valid value (several rows in the actual
  workbook are flight-school tandem flights taken for free) — must render as "0", not as "not recorded".
- An XContest export entry whose date has no imported flight at all (a flight logged on XContest that
  was never in the Excel, or predates it): reported as unmatched, never creates a new flight row —
  this feature only enriches existing flights, it does not import new ones from XContest.
- Re-running either import (secondary sheets or XContest) after the pilot has since edited or deleted an
  affected flight: the import must not resurrect, recreate, or crash on a now-missing reference — report
  it as unresolved, consistent with FR-009/FR-002's existing ambiguity-handling rule.
