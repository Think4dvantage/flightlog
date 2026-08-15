# Resume Notes — 2026-08-15

## In Progress

**v0.5.0 remains shipped and confirmed live** (unchanged since the last update — see git history for
that session's detail if needed). **New this pass: the full spec → research → data-model → contracts →
plan → tasks cycle for all four remaining roadmap milestones (`v0.6` through `v0.9`) is now written,
committed, and pushed — none of it implemented yet.** This was done autonomously overnight at the
pilot's explicit request ("prepare 0.6 until 0.9 so that we are ready to implement all of it"); per
`00-ai-usage.md`'s Planning Mode rule, planning stopped at the plan — no code was written for any of the
four.

**`specs/004-secondary-sheets-xcontest/` (v0.6)**: hikes/ground-handling/tandem-flights/goals import
plus XContest score attachment. Grounded in a first-ever direct read of the four secondary sheets
(`Fitnessprogramm`/`Groundhandling`/`Tandemflüge`/`Ziele` — named but never actually read in `v0.2`'s own
planning). The XContest "My Flights" export JSON schema is still genuinely unknown — investigated the
pilot-supplied `Iv/FlyHigh` repo, which turned out to implement the opposite direction (flight *upload*/
scoring-submission, not the *list-retrieval* this feature needs) — flagged as an explicit Phase 1
research item (obtain one real sample export), not guessed.

**`specs/005-statistics/` (v0.7)**: the full stats catalogue, no new tables (matches
`architecture.md`'s existing non-speculative-caching stance). Grounded in a full read of the real
`Übersicht` sheet (previously only its region-count/reverse-launch-share blocks had been read) — pins
down the exact personal-best figures and duration-bucket boundaries already in real use. Found a third
confirmed workbook disagreement while researching: the sheet's own "Buddys" tally uses a different name
set and different counts than the frozen comment-scan buddy proposals from `v0.2`'s import — resolved by
scoping the per-buddy stat to only ever read live `flight_buddies` rows, never reconciling the two
historical sources.

**`specs/006-public-api-vidfactory/` (v0.8)**: scoped API keys, the frozen `/api/integration/v1` surface,
`flight_links` push-back. Caught a real doc/reality gap: `01-project-overview.md` and
`02-backend-conventions.md` both describe `get_api_principal`/`require_scope`/`ApiPrincipal` as though
already implemented — confirmed against the real `dependencies.py` that none of it exists yet. Also
resolved a genuine inconsistency between the two docs (one says API keys can be "unexpired," the other's
schema has no expiry column) by adding a nullable `expires_at`.

**`specs/007-sharing-public-readiness/` (v0.9)**: per-flight visibility, public profile, rate limiting,
plus the real remaining self-registration gap. Caught two more stale roadmap items: buddy invite/accept
has been shipped since `v0.2`, and `allow_self_registration` is already a working flag — neither is part
of this feature as originally worded. What's actually still open, found via `auth.py`'s own dead
comment: a self-registered account today gets zero flight categories and can't log a flight at all,
since generic starter-category seeding was explicitly deferred to this exact point. **The git-history
scrub of `olddata/Flugbuch.xlsx` is named as a hard prerequisite for this milestone but deliberately has
no task in `tasks.md`** — a history rewrite is destructive and effectively irreversible, and stays a
separately pilot-confirmed action, never bundled into routine implementation.

**Three small roadmap corrections made to `features.md` along the way** (not code changes): v0.6's entry
now explicitly owns the `/goals` page (v0.7's original wording had listed it too, from before that
overlap was noticed); v0.9's entry had two already-shipped items removed from its description.

## Next Step

1. **Implement in roadmap order — v0.6 first.** Each spec's own `tasks.md` is the authoritative,
   dependency-ordered breakdown; start with Phase 1 of `specs/004-secondary-sheets-xcontest/tasks.md`.
2. **v0.6's Phase 1, T001 needs a real XContest "My Flights" export sample from the pilot** before its
   parser can be written with confidence — this is a genuine blocker for that one sub-feature (not for
   the hikes/ground-handling/tandem-flights/goals import, which has no such dependency).
3. **Config tuning on the shipped `v0.5` IGC parsing may need iteration** — the defaults are `libigc`'s
   own sailplane-tuned values; still unconfirmed whether the pilot's real thermal/glide figures from
   their live uploads look right against what they remember of those flights.
4. **Decide on `specs/002-flight-log-ui`'s Phases 9–11** (`/contacts`, CSV export, remember-last-filters)
   — still open, not tied to any particular tag; can slot in alongside any of `v0.6`–`v0.9` whenever
   convenient.

## Open Questions

- Which of `v0.6`–`v0.9` to actually implement first isn't fully forced — `tasks.md`'s own dependency
  diagrams show `v0.7`/`v0.8`/`v0.9` don't strictly need `v0.6` to exist first at the code level, only at
  the roadmap-ordering level. Worth a deliberate call rather than assuming strict roadmap order if the
  pilot has a reason to prioritize differently (e.g. the API/VidFactory integration if that's blocking
  someone else's work).
- When Phases 9–11 ship — see step 4 above.
- `features.md`'s backlog, unchanged this session: grant the deploy `gh` token `read:packages`, the
  `bootstrap_admin_email`/`bootstrap_admin_password` `set=%s`-style logging gap.

## Context

- **Every milestone from `v0.6` through `v0.9` now has a complete spec/research/data-model/contracts/
  plan/tasks set** in `specs/004-secondary-sheets-xcontest/`, `specs/005-statistics/`,
  `specs/006-public-api-vidfactory/`, `specs/007-sharing-public-readiness/` — read the relevant
  `research.md` before touching any of these; each one records real findings (actual sheet structures,
  actual repo-code inspection, actual PyPI version checks) that would otherwise need re-deriving.
- **A running theme across all four plans, worth remembering for the next one too**: this session
  repeatedly found that a design doc or an old spec's prose had drifted from reality (stale roadmap
  version numbers, `01-project-overview.md`/`02-backend-conventions.md` describing code that doesn't
  exist, `Übersicht`'s untouched blocks, XContest's real API turning out to be a different repo's
  different direction). Verify against the real source — code, real files, real PyPI/GitHub metadata —
  before designing on top of any existing doc's claims, including this file's own claims once enough
  time has passed.
- **`v0.5`'s own spec/tasks still live in `specs/003-igc-ingest-analysis/`**, 35/35 checked off — no
  longer the active work, kept for reference.
- **The dev server needs a restart after every backend edit** (no `--reload`). See
  [[flightlog-dev-server-workflow]].

This file is a pointer, not a duplicate — `.ai/context/features.md`, `architecture.md`, and each
feature's own `specs/` folder have the detail.
