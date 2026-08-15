# Feature: Statistics

## Overview

Gives a pilot the full statistical picture of their flying career in one place — the numbers the legacy
spreadsheet's `Übersicht` tab hand-computed with formulas, reproduced correctly (including fixing two
already-confirmed formula bugs) and extended with figures the spreadsheet could never produce at all
(cumulative thermal climb from real IGC tracks). Nothing here is new data — every figure is computed
from `flights`, its related tables, and `igc_tracks`, on read.

## Clarifications

### Session 2026-08-15
- Q: The real workbook's `Übersicht` sheet has its own "Buddys" tally block (`Tom` 141, `Ueli` 61,
  `Simon` 16, `Päsci` 36) — a different name set entirely from `core/aliases.py`'s `KNOWN_BUDDY_NAMES`
  used for the v0.2 import's comment-scan buddy proposals (`Tom` 134, `Ueli` 61, `Simon` 16, plus
  `Susi`/`Tigi`/`Jürg`/`Beni`, none of which appear in `Übersicht`'s own block). Since buddy tags on a
  flight are only ever pilot-created going forward and were never auto-created from either source
  (v0.2's FR-017), what should the per-buddy statistic be computed over? → A: Only ever the
  `flight_buddies` rows that actually exist at query time — never an attempt to reconstruct or backfill
  historical buddy tags from either the workbook's tally or the frozen comment-scan proposals. A
  per-buddy statistic legitimately starts sparse (most historical flights untagged) and fills in only as
  the pilot tags flights going forward; this is a known, accepted limitation, not a defect to work
  around in this feature.
- Q: `/goals` was originally pencilled in as a `v0.7` deliverable alongside `/stats`
  (`features.md`'s pre-existing roadmap text), but the `goals` table and its full CRUD page were already
  scoped and spec'd under `v0.6` (`specs/004-secondary-sheets-xcontest`) once that feature's planning
  actually happened. → A: `/goals` is a `v0.6` deliverable, already fully spec'd there — not
  re-scoped or duplicated here. This feature is `/stats` only, matching `features.md`'s own
  since-corrected v0.6 entry.

## User Stories

### P1 — Must Have

**As a pilot, I want to see career totals and averages so I know the overall shape of my flying without
adding up 600 rows by hand.**

Acceptance Criteria:
- Total flights, total airtime, total distance, total altitude gain, average airtime, average distance.
- A second "average airtime, excluding training" figure alongside the plain average — the spreadsheet's
  own "Average Airtime special" distinction (`architecture.md`), reproduced, not reinvented.
- Every total/average is correct against the full flight set at the time of viewing — not a stale
  snapshot (unlike `/import`'s deliberately frozen historical report).

**As a pilot, I want to see my flying broken down by year and by month so I can see how my flying has
changed over time and which months are my most active.**

Acceptance Criteria:
- A flights-per-year figure and a flights-per-month figure.
- A combined year × month matrix (the workbook's own "Distribution over Time" block, reproduced).
- A distance/duration/altitude distribution view (histogram-style buckets) — using the workbook's own
  observed bucket boundaries (30 / 60 / 120 / 180 minutes) as the baseline duration buckets, since
  they're already a real, meaningful breakdown a pilot has looked at before.

**As a pilot, I want to see my personal bests, each linking back to the actual flight, so I can revisit
the flight behind any given record.**

Acceptance Criteria:
- Longest airtime, highest max altitude, highest launch, lowest launch, highest landing, lowest
  landing, longest distance, shortest distance — the exact set the workbook's own "Flight Statistics"
  block already tracks.
- Every personal best is a link to its flight's detail page, not just a bare number.

**As a pilot, I want to see per-year matrices broken down by launch site, region, glider, harness, and
flight category so I can see which gear and places dominate my flying history, year by year.**

Acceptance Criteria:
- Five matrices, one per dimension (site, region, glider, harness, category), each showing a per-year
  breakdown — mirroring the workbook's own "Launch Statistics" / "Landing Statistics" / "Flight Area" /
  "Glider Types" / "Harness Types" / "Flight Type" blocks, all of which already exist as real,
  previously-used views of this exact data.
- A launch-technique (forward/reverse) split, matching the workbook's own "Launch Direction" block.
- Hike&Fly totals, drawing on the existing `flight_categories.is_hike_fly` flag (`architecture.md`).

### P2 — Should Have

**As a pilot, I want to see cumulative thermal climb and other IGC-derived rollups so I get a headline
number the spreadsheet was never able to produce.**

Acceptance Criteria:
- A cumulative thermal climb total, summed across every uploaded track's kept thermal segments
  (`specs/003-igc-ingest-analysis`'s already-filtered thermal data — descending spirals/wingovers
  already excluded at the source).
- This figure is computed over whatever tracks are actually uploaded — it is explicitly not expected to
  cover 100% of historical flights, since IGC upload is itself optional and incremental.

**As a pilot, I want to see my per-buddy year matrix, streaks, and year-to-date pace so I can track
momentum and who I fly with most, going forward.**

Acceptance Criteria:
- A per-buddy year matrix, computed only over `flight_buddies` rows that exist (see Clarifications) —
  legitimately sparse for historical flights never tagged.
- A current flying streak (consecutive weeks/months with at least one flight) and a year-to-date pace
  comparison against the same point in a prior year.
- A cumulative-flights-over-time progression series (a running total by date), suitable for a simple
  line chart.

### P3 — Nice to Have

**As a pilot, I want the statistics view to be shareable or exportable so I can show a season summary to
someone else without giving them access to my whole log.**

Acceptance Criteria: out of scope for this feature — a public/shareable stats view depends on `v0.9`'s
visibility model, which doesn't exist yet. Recorded here only so the intent isn't lost.

## Functional Requirements

- FR-001: The system MUST show total flights, total airtime, total distance, and total altitude gain,
  computed live over the current flight set.
- FR-002: The system MUST show average airtime and average distance, plus a second average-airtime
  figure excluding training-flagged flights.
- FR-003: The system MUST show a flights-per-year, flights-per-month, and combined year × month
  breakdown.
- FR-004: The system MUST show duration, distance, and altitude distributions using bucketed ranges.
- FR-005: The system MUST show the eight personal-best figures named in the P1 stories, each linking to
  its underlying flight.
- FR-006: The system MUST show per-year matrices for launch site, region, glider, harness, and flight
  category.
- FR-007: The system MUST show a launch-technique (forward/reverse) split and separate Hike&Fly totals.
- FR-008: The system MUST show a cumulative thermal-climb rollup computed from uploaded IGC tracks'
  kept thermal segments.
- FR-009: The system MUST show a per-buddy year matrix, computed only over existing `flight_buddies`
  associations — never inferred or backfilled from any other source.
- FR-010: The system MUST show a current streak, a year-to-date pace comparison, and a cumulative
  flights-over-time progression series.
- FR-011: Every figure MUST be computed on read from existing data — this feature introduces no new
  persisted statistic, and no cached/materialized table unless a specific figure is later found to
  measurably exceed the existing project-wide ~200ms performance bar (`architecture.md`).
- FR-012: All user-visible chrome MUST go through the existing translation mechanism.
- FR-013: The `/stats` page MUST use the existing dark theme and navigation shell.

## Non-Functional Requirements

- NFR-001: The full `/stats` page must load in well under a second against the current flight count
  (~600 rows) and continue to perform acceptably as flight count grows — matching
  `specs/002-flight-log-ui`'s existing NFR-001 precedent for this app's scale expectations.
- NFR-002: Every view introduced by this feature must be usable by keyboard alone.
- NFR-003: A page rendering with zero flights, zero IGC tracks, or zero tagged buddies (a brand-new
  account, or filtered views with no matches) must show a clear empty/zero state for each affected
  figure, never a broken calculation, a crash, or a misleading blank.

## Success Criteria

- A pilot can answer "how is my flying trending, and what are my personal records" without ever opening
  the spreadsheet or doing arithmetic by hand.
- Every figure this feature reproduces from the workbook's own `Übersicht` tab either matches it exactly
  or, where a known formula bug exists in the workbook (reverse-launch % computed over a stale range;
  the 596-vs-600 region-count gap; the buddy-tally name-set/count mismatch discovered while planning
  this feature), the app's own figure is confirmed correct and the discrepancy is understood, never
  silently "fixed" to match the spreadsheet's wrong number.
- The cumulative thermal-climb figure exists and is visibly a number the spreadsheet could never have
  produced, fulfilling this milestone's stated reason for existing (`features.md`).

## Key Entities

No new persisted entities (`architecture.md`'s existing `stats_cache` non-table decision — nothing is
materialized speculatively). Every figure is a read-time aggregate over: `flights` (+ its computed
`alt_gain_m`/`site_drop_m`/`total_descent_m`), `flight_categories`, `sites`, `regions`, `gliders`,
`harnesses`, `buddies`/`flight_buddies`, and `igc_tracks`/`igc_segments`.

## Out of Scope

- Any new stored/cached statistics table — revisit only if a specific real-world query is measurably too
  slow, per the project's existing non-speculative-caching rule.
- `/goals` (already shipped as part of `v0.6`, see Clarifications).
- A public or shareable statistics view (`v0.9`'s visibility model, not yet built).
- Weather/conditions-aware anything (`v0.10`).
- Backfilling historical buddy tags, or reconciling the workbook's "Buddys" tally against the comment-
  scan proposals — both are read as informative planning context only; neither becomes new data written
  by this feature (see Clarifications).
- Recomputing or second-guessing the workbook's own historical figures beyond the three already-known/
  newly-discovered disagreements — this feature confirms and displays correct figures, it does not
  audit the entire spreadsheet line by line for further discrepancies.

## Assumptions

- There is exactly one pilot account in the system today (matches every prior feature's assumption).
- IGC track coverage is partial and will remain so for older flights — the cumulative thermal-climb
  figure and any other IGC-derived rollup is understood by the pilot to reflect only flights with an
  uploaded track, not the full historical flight count.
- The exact bucket boundaries for distance/altitude distributions (unlike duration, which the workbook
  already suggests via its "# of Flights over Nmin" figures) are a planning-to-implementation detail, not
  a product decision requiring further clarification — reasonable round-number buckets are sufficient.

## Dependencies

- Requires `flights` and its computed altitude figures (v0.2), `flight_categories.is_hike_fly`/
  `is_training` flags (v0.2), `sites`/`regions`/`gliders`/`harnesses`/`buddies` (v0.2), and
  `igc_tracks`/`igc_segments` (v0.5) — this feature reads all of them, adds none.
- Requires `flight_buddies` (v0.2) for the per-buddy matrix, understanding it will be sparse for
  historical data (see Assumptions).

## Edge Cases

- A brand-new pilot account with zero flights: every figure must show a clear empty state, not a
  division-by-zero error or a blank page (NFR-003).
- A flight with no glider/harness/landing site recorded (already-existing optional fields): must not
  break a matrix that groups by that dimension — it should appear as its own "not recorded" bucket
  within the matrix, or be excluded from that specific matrix with the totals still correct elsewhere.
- A personal-best figure with a tie (e.g. two flights at the exact same max altitude): links to one of
  the tied flights consistently (e.g. the earliest by date), not a nondeterministic choice on every
  page load.
- The cumulative thermal-climb figure when zero tracks are uploaded yet: shows a clear "no tracks
  uploaded yet" state, not a bare "0" that reads as "you have never climbed in a thermal."
