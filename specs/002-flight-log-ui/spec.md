# Feature: Flight Log UI

## Overview

A pilot-facing web UI that fully replaces `Flugbuch.xlsx`: a searchable, filterable, sortable flight log
with inline add/edit, a site catalogue with map pin-drop, equipment and contacts management, a one-time
read-only review of what the historical spreadsheet import found, and a CSV export. This is the MVP
boundary for the project — once it ships, the spreadsheet is never opened again for day-to-day use.

## Clarifications

### Session 2026-08-07
- Q: What should the `/import` review page do? → A: Read-only historical report of the v0.2 import's
  findings (unresolved harness, buddy-name proposals, region/altitude mismatches). No actions on the
  page itself — the pilot resolves each item using the normal flights/equipment/contacts UI.
- Q: What does CSV export cover? → A: Always the full flight log with a fixed column set, regardless of
  the list's current search/filter/sort state.
- Q: Does `/contacts` include buddy account linking (invite/accept/decline)? → A: No — simple CRUD of a
  buddy by display name only. Account linking is out of scope for this feature (see Out of Scope).

## User Stories

### P1 — Must Have

**As a pilot, I want to browse all my flights in a searchable, filterable, sortable, paginated list so
I can find any flight without opening a spreadsheet.**

Acceptance Criteria:
- Free-text search matches launch site, landing site, category, glider, and notes.
- Filters: year, category, glider, launch site, region — usable independently or combined.
- Every column is sortable (date, duration, distance, max altitude, computed altitude gain); default
  sort is most recent flight first.
- Results are paginated; the current filter/search/sort state is reflected in the page's URL so a link
  to a filtered view can be shared or bookmarked.
- An empty result set shows a distinct "no flights match" state, not a blank table.

**As a pilot, I want to add and edit a flight without leaving the list so logging a flight is as fast as
a spreadsheet row.**

Acceptance Criteria:
- An add/edit panel opens over the list (not a full page navigation) for both creating a new flight and
  editing an existing one.
- Every stored flight field is editable: date, launch site, landing site, category, glider, harness,
  duration, distance, max altitude, launch technique, notes, and tagged buddies.
- Launch site and category are required; every other field is optional, matching existing data rules.
- Validation errors are shown next to the specific field that failed, not just as a generic banner.
- Saving updates the list in place without a full page reload; the newly added/edited row is visibly
  highlighted or scrolled into view.
- Deleting a flight requires an explicit confirmation step.

**As a pilot, I want a detail view for a single flight so I can see everything about it in one place.**

Acceptance Criteria:
- Reachable by a stable, linkable URL per flight.
- Shows every stored field plus the computed figures (altitude gain, site drop, total descent).
- Shows the resolved names (not raw IDs) of launch site, landing site, category, glider, harness, and
  tagged buddies, each linking to that entity where a corresponding page exists.
- A flight with a missing optional reference (e.g. no glider recorded) displays a clear "not recorded"
  state rather than a blank or broken field.

**As a pilot, I want to manage my launch and landing sites, including dropping a pin on a map, so my
site list matches reality.**

Acceptance Criteria:
- Lists all sites (already populated from the historical import) with their launch/landing flags.
- A map view lets the pilot manually place or move a pin for a site that doesn't yet have coordinates.
- A site with no coordinates yet (the large majority, until track-based backfill ships later) is clearly
  distinguishable from one with a manually-placed or track-derived pin.
- Editing a site's name or elevation does not require re-placing its pin.

**As a pilot, I want to manage my gliders and harnesses so my equipment list stays current.**

Acceptance Criteria:
- Create, edit, and retire a glider or harness.
- A retired item is visually distinguished from active gear and excluded from the default choices
  offered when adding a new flight, but remains fully visible and correct on any historical flight that
  references it.

**As a pilot, I want a read-only summary of what the historical spreadsheet import found so I know
exactly what to clean up.**

Acceptance Criteria:
- Shows, verbatim from the completed v0.2 import: the unresolved-gear items (flights whose harness
  couldn't be matched to current equipment), the region-count and altitude-figure discrepancies against
  the old spreadsheet, and the buddy names proposed from flight comments.
- Presents this as historical/reference information only — the page itself performs no import, write,
  or resolution action. The pilot acts on each item through the flights, equipment, and contacts pages.

### P2 — Should Have

**As a pilot, I want to manage a simple contacts list of flying buddies so I can tag who I flew with.**

Acceptance Criteria:
- Create, edit, and delete a contact by display name.
- A contact shows how many flights it is tagged on.
- Deleting a contact removes the tag from any flight it was attached to, without deleting the flight.

**As a pilot, I want to export my full flight log to CSV so I have an offline copy.**

Acceptance Criteria:
- A single export action produces a CSV of every flight, with a fixed, documented column set — not
  limited to whatever the list's current search/filter/sort happens to show.
- The exported file opens correctly in a common spreadsheet application without manual encoding fixes
  (German characters in site/category/gear names render correctly).

### P3 — Nice to Have

**As a pilot, I want the flights list to remember my last-used filters and sort when I come back to it**
so I don't have to reapply them every session.

## Functional Requirements

- FR-001: The system MUST provide a flights list view with free-text search across launch site, landing
  site, category, glider, and notes.
- FR-002: The system MUST let the pilot filter the flights list by year, category, glider, launch site,
  and region, independently or in combination.
- FR-003: The system MUST let the pilot sort the flights list by any displayed column, ascending or
  descending, defaulting to most-recent-first.
- FR-004: The system MUST paginate the flights list.
- FR-005: The system MUST let the pilot create a new flight and edit an existing flight from within the
  flights list view, without a full page navigation.
- FR-006: The system MUST validate flight input server-side and surface validation errors attached to
  the specific field that failed.
- FR-007: The system MUST require an explicit confirmation before deleting a flight.
- FR-008: The system MUST provide a per-flight detail view, reachable by a stable URL, showing every
  stored field and the computed altitude-gain, site-drop, and total-descent figures.
- FR-009: The system MUST provide a sites view listing all sites with their launch/landing flags.
- FR-010: The system MUST let the pilot manually set or move a site's map coordinates via pin drop.
- FR-011: The system MUST visually distinguish a site with no coordinates from one with a pin.
- FR-012: The system MUST provide an equipment view where the pilot can create, edit, and retire
  gliders and harnesses.
- FR-013: The system MUST exclude retired equipment from default selection when adding a new flight,
  while preserving retired equipment as a valid, correctly-displayed reference on historical flights.
- FR-014: The system MUST provide a read-only view of the v0.2 historical import's findings: unresolved
  gear, region-count discrepancies, altitude-figure discrepancies, and buddy-name proposals.
- FR-015: The import-findings view MUST NOT perform any write, re-import, or resolution action itself.
- FR-016: The system SHOULD provide a contacts view where the pilot can create, edit, and delete a buddy
  by display name, and see how many flights each contact is tagged on.
- FR-017: Deleting a contact MUST remove its tag from any flight without deleting the flight itself.
- FR-018: The system SHOULD provide a single CSV export of the full flight log, with a fixed column set,
  independent of the flights list's current search/filter/sort state.
- FR-019: All user-visible chrome (labels, buttons, navigation, validation messages) MUST go through the
  existing translation mechanism; user-entered data (site names, gear names, categories, notes) MUST
  never be translated.
- FR-020: Every page introduced by this feature MUST use the existing dark theme and navigation shell
  consistently with the rest of the application.

## Non-Functional Requirements

- NFR-001: The flights list must remain responsive (interactions complete in well under a second) with
  the current full flight count (~600 rows) and continue to scale as new flights are logged.
- NFR-002: Every view introduced by this feature must be usable by keyboard alone (tab order, focus
  handling on the add/edit panel, escape-to-close).
- NFR-003: Destructive actions (flight delete, contact delete, equipment retire) must be recoverable
  from user error via an explicit confirmation step; none may be a single accidental click.

## Success Criteria

- A pilot can find any of the 600 historical flights through search/filter/sort in under 10 seconds,
  without knowing its row number or exact date.
- A pilot can log a new flight entirely through the UI, in less time than opening and editing the old
  spreadsheet.
- A pilot can identify, from the import-findings view alone, every data-quality item left over from the
  historical migration, without reading server logs or the codebase.
- The spreadsheet (`olddata/Flugbuch.xlsx`) is not required for any task a pilot performs day-to-day
  after this feature ships.

## Key Entities

No new entities. This feature is a UI layer over data already modelled and populated as of v0.2:
`flights`, `sites`, `gliders`, `harnesses`, `flight_categories`, `buddies`, `regions`. The read-only
import-findings view surfaces facts already established by the completed v0.2 import (see
`specs/001-core-data-import/` and `RESUME.md`); it does not introduce a new stored entity for those
findings unless the planning phase determines that's the only way to reproduce them reliably.

## Out of Scope

- Buddy account linking (invite by email, accept/decline, linked-account display-name reveal) — the
  buddies data layer already supports it, but the UI for it is deferred; v0.8's backlog already lists a
  dedicated "buddy invite/accept flow" as its own milestone.
- Anything IGC: track upload, map track rendering, thermal/glide analysis, barogram.
- Anything statistics: totals, averages, distributions, personal bests, streaks, `/stats`, `/goals`.
- Sharing: flight visibility, public flight pages, public pilot profiles.
- The secondary Excel sheets: hiking, ground-handling, tandem flights, goals.
- XContest import.
- Filtered or column-selectable CSV export (fixed full-log export only, per Clarifications).
- Any write path back into the historical import process — the workbook is not re-opened by this
  feature.

## Assumptions

- There is exactly one pilot account in the system today (matches v0.2's stated assumption); this
  feature does not need to handle multi-pilot data isolation in its UI beyond what already exists in the
  data layer.
- The exact set of CSV columns is a planning-phase decision, not a product decision requiring further
  clarification — a reasonable default covering all directly-stored and computed flight fields is
  sufficient.
- Map tiles/base layer for the site pin-drop map use the same self-hosted approach already in place for
  any other mapping in this project (no new external map-tile dependency decision is being made by this
  spec).
- Search is case-insensitive and matches substrings, not just whole words or prefixes.

## Dependencies

- Requires the data and record-level operations for flights, sites, gliders, harnesses, categories, and
  buddies already delivered in v0.2 — this feature adds no new domain data operations beyond what those
  already support, except whatever is needed to reproduce the import-findings view (a planning-phase
  decision).
- Requires the existing authentication, navigation, theming, and translation machinery already shipped
  in v0.1/v0.2.

## Edge Cases

- A flight with no landing site, glider, or harness recorded (optional fields) must still render
  correctly everywhere it appears (list, detail, edit panel) with a clear "not recorded" state, not a
  blank cell or a broken computed figure.
- A site used as both a launch and a landing (the schema explicitly allows this — see
  `context/architecture.md`) must display correctly in both roles without appearing as two entries.
- Deleting the only glider or harness referenced by historical flights must not delete or corrupt those
  flights — the reference becomes null with the "not recorded" state, consistent with existing gear
  resolution rules.
- A newly added flight whose launch site does not yet exist must offer a way to create that site inline,
  without forcing a context switch to the sites page and back.
- The import-findings view must render sensibly even though the underlying findings reference data
  (flight rows, gear names) that may since have been edited or deleted by the pilot through this same
  feature — findings are a historical snapshot, not a live query that could contradict itself.
