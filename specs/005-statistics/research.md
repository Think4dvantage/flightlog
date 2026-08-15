# Research: Statistics

Findings from inspecting the real `Übersicht` sheet directly (via `openpyxl`), going beyond what
`specs/001-core-data-import/research.md` and `architecture.md` had already read from it (the region
counts and reverse-launch share blocks only) — the full sheet turns out to be a hand-built stats
dashboard already, block by block, and is the primary grounding for this feature's exact figure list.

## Decision: the workbook's own `Übersicht` blocks are the ground truth for what to build, not `features.md`'s prose alone

- **Decision**: `Übersicht`'s real blocks — `Distribution over Time` (year × month matrix),
  `Flight Statistics` (averages, personal bests, totals, duration-threshold counts), `Launch Statistics`,
  `Landing Statistics`, `Flight Area` (regions), `Flight Type` (categories), `Glider Types`,
  `Launch Direction`, `Harness Types`, and `Buddys` — map directly onto `spec.md`'s FR list, and were
  used to pin down the *exact* set of personal-best figures (longest airtime, max altitude, highest/
  lowest launch, highest/lowest landing, longest/shortest distance) and the *exact* duration-bucket
  boundaries already in real use (30 / 60 / 120 / 180 minutes, from the `# of Flights over Nmin` rows)
  rather than inventing either list from `features.md`'s more general prose.
- **Rationale**: These aren't arbitrary choices — they're what the pilot has actually looked at and
  cared about for years, sitting right there in the source file. Reusing them is both less design work
  and a better product decision than inventing a fresh figure list.
- **Confirms, does not contradict, `architecture.md`'s existing "Average Airtime special" note**: the
  real sheet's row 17 (`Average Airtime` = 26.135) and row 18 (`Average Airtime special` =
  28.560253699788582) match `architecture.md`'s already-documented `26.14`/`28.56` almost exactly (the
  small differences are float display rounding) — confirms the existing
  `AVG(duration) WHERE NOT is_training` definition rather than discovering anything new about it.

## Decision: a third confirmed workbook disagreement — the "Buddys" tally uses a different name set and different counts than the comment-scan buddy proposals, and this feature does not reconcile it

- **Finding**: `Übersicht`'s own `Buddys` block tracks four names with per-year flight counts:
  `Tom` (141), `Ueli` (61), `Simon` (16), `Päsci` (36). The v0.2 import's comment-text-scan buddy
  proposals (`core/aliases.py`'s `KNOWN_BUDDY_NAMES`, frozen in `core/import_history.py`'s
  `HISTORICAL_IMPORT_SUMMARY.buddy_proposals`) cover a *different* set: `Tom` (134), `Ueli` (61),
  `Simon` (16), plus `Susi` (24), `Tigi` (12), `Jürg` (3), `Beni` (2) — and **`Päsci` never appears in
  the comment-scan list at all**. `Ueli` and `Simon` happen to match exactly across both mechanisms;
  `Tom` does not (141 vs. 134, a 7-flight gap).
- **Root cause, confirmed by mechanism, not just by the numbers**: the workbook's `Buddys` block is
  almost certainly a manually-maintained tally (a dedicated column or manual count the pilot kept
  directly), while the comment-scan proposals are a *derived* signal (regex word-boundary matching
  against free-text `Kommentar` cells, `core/importer.py`'s `_find_buddy_mentions`) — two genuinely
  different data sources describing the same real-world fact, not one process with a bug. Neither is
  "wrong" in the way the region-count and reverse-launch-share disagreements are (those are confirmed
  formula bugs in the workbook); this is a data-provenance difference.
- **Decision**: this feature's per-buddy matrix computes **only over `flight_buddies` rows that
  actually exist in the database at query time** — never an attempt to reconcile, backfill, or "fix"
  historical counts from either source. This is also forced by v0.2's own FR-017 (`buddies` rows and
  their flight tags are never auto-created) — as of today, it is very likely **zero** historical
  flights have any `flight_buddies` row at all, since nothing has ever written one except a pilot
  manually tagging a flight through the `/flights` drawer's buddy multi-select (shipped `v0.3`). A
  per-buddy statistic starting near-empty is the correct, expected behavior, not a bug to route around.
- **Alternatives considered**: Bulk-creating `Buddy` rows and retroactively tagging flights from the
  frozen `buddy_proposals` data to give the per-buddy matrix real historical depth immediately.
  Rejected — this is exactly the kind of one-time historical-data operation that belongs to the
  buddies/contacts feature itself (already flagged as open, undecided-priority backlog in
  `specs/002-flight-log-ui`'s Phases 9–11), not to a statistics *display* feature. Scope creep here
  would also mean writing new `flight_buddies` data from a comment-scan heuristic FR-017 explicitly
  never wanted to be authoritative enough to auto-create from.

## Decision: total/cumulative altitude figures are computed from the app's own derived values, never from the workbook's stored `Altgain` column

- **Decision**: any "Total Altgain" or per-flight altitude-gain figure this feature shows sums the
  app's own computed-on-read `alt_gain_m` (`architecture.md`'s "Derived values" section) across flights
  — never the workbook's own stored `Altgain` figures, even though `Übersicht`'s `Flight Statistics`
  block does show a `Total Altgain (m)` of 61191 for reference.
  - **Rationale**: `architecture.md` already documents a confirmed, real disagreement at row 387
    (stored `Altgain` 350 vs. the correct computed value 0) — the workbook's own historical figure is
    already known to be unreliable in at least one row. The whole reason `alt_gain_m` is computed on
    read instead of stored is so a site-elevation correction retroactively fixes every flight that used
    it; trusting a stale imported number here would silently reintroduce the exact problem that design
    already avoids everywhere else in the app.

## Decision: cumulative thermal climb sums `igc_segments.alt_change_m` for `kind = "thermal"` rows directly — no new filtering needed

- **Decision**: the "headline number the Excel cannot produce" (`features.md`) is
  `SUM(igc_segments.alt_change_m) WHERE kind = 'thermal'`, joined across every track the pilot owns.
- **Rationale**: `specs/003-igc-ingest-analysis`'s `core/igc.py` already filters thermals down to
  genuinely climbing circles before a segment is ever persisted (`architecture.md` rule 3: "keep only
  climbing circles... `[t for t in flight.thermals if t.alt_change() > 0]`") — every stored `thermal`
  segment's `alt_change_m` is already guaranteed positive. This feature does no additional filtering; it
  is a plain, direct aggregate over already-clean data, which is exactly why it was worth building
  `v0.5` first.

## Decision: one shared "dimension × year" matrix query shape, not five near-duplicate endpoints

- **Decision**: `core/stats.py` exposes one internal helper —
  `year_matrix(db, owner_id, group_by: Literal["site", "region", "glider", "harness", "category"])` —
  that every per-dimension matrix (FR-006) calls with a different grouping column, rather than five
  independently hand-written SQL aggregates. The API surface can still expose five separate endpoints
  (one per dimension, per `contracts/endpoints.md`) if that's the cleanest response shape for the
  frontend — the sharing happens at the query-construction level, not necessarily the HTTP level.
- **Rationale**: `Übersicht`'s five matrix blocks (Launch/Landing/Area/Type/Glider/Harness Statistics)
  are structurally identical — a dimension name, a per-year count — differing only in which column is
  grouped on. Writing this once, parameterized, avoids five copies of the same `GROUP BY flight_date
  year, <dimension>` logic drifting independently over time.
- **Alternatives considered**: Five fully independent router functions with their own inline queries.
  Rejected as the kind of duplicated-logic risk `04-constraints.md`'s general code-quality guidance
  already warns against — five copies of the same shape is worse than one parameterized helper for
  something this structurally repetitive.

## Decision: personal-best ties resolve to the earliest flight by date

- **Decision**: when more than one flight ties for a personal-best figure (e.g. two flights at the same
  max altitude), the linked flight is deterministically the one with the earliest `flight_date` (ties
  within the same date broken by `id` for total determinism).
- **Rationale**: `spec.md`'s Edge Cases requires determinism across page loads; "earliest" is an
  arbitrary but simple, stable, and defensible tiebreak — it reads naturally as "the flight that first
  set this record."
