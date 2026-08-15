# Implementation Plan: Sharing & Public Readiness

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Backend-first, on the existing stack, plus one new dependency. FastAPI + Pydantic v2 + SQLAlchemy 2.0
(two new columns, one new router, one small extension to the existing flights router); `slowapi` 0.1.10
(new, verified-current dependency, `research.md`) for rate limiting; vanilla-JS ES modules for two new
unauthenticated-facing pages, following the existing conventions but explicitly *not* assuming a logged-
in session the way every prior page did.

**Architecture approach**: this is the first genuinely public (unauthenticated, rate-limited) data-
serving surface in the app — `health.py` is public but serves no pilot data at all. Every design choice
here (its own router, no auth dependency present at all, `slowapi` limiting, the never-leak-existence
404 shape) follows that precedent while extending it into real data exposure for the first time, which
is exactly why this milestone is named "public *readiness*," not just "sharing."

**Performance**: NFR-001 wants the public surface to load as fast as the authenticated one — no special
caching is introduced; the same indexed queries every other flight/profile read already uses apply here
too, just with a `visibility`/`public_profile_enabled` filter added.

**Security**: the highest-stakes feature after `v0.8`'s API keys, for a different reason — this is the
first surface literally anyone on the internet can hit with zero credential. Every response shape must
be reviewed specifically for accidental data leakage (a public flight response must not accidentally
include another private field the existing `FlightOut` schema happens to carry).

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, every `.ai/instructions/` file, `architecture.md`'s Sites/Buddy-linking sections, the real `buddies.py` and `auth.py`/`config.py` (confirming two roadmap items already shipped, `research.md`), `specs/001-core-data-import/research.md` (confirming the deferred category-seeding gap), all read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | No username/slug system (reuses the existing opaque UUID, `research.md`); no view-count analytics (P3, deferred); no retroactive rate-limiting of already-public `/health` (spec's Assumptions); the buddy-linking and self-registration-flag items already shipped are correctly *not* re-built here |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`) |
| No secrets committed | N/A |
| Prod is off-limits | N/A — local implementation; deployment follows the existing tag-push pipeline. **The git-history scrub named in `spec.md` is explicitly not a deployment-pipeline action either** — it's a one-time, manually-confirmed local operation before the repository's own visibility ever changes, per `research.md` |

No violations.

## Data Model Summary

Two new columns (`flights.visibility`, `users.public_profile_enabled`) on existing tables — both need
`_run_column_migrations()`'s idempotent guard. No new tables. Full detail in `data-model.md`.

## File Structure

### Backend (new)
```
src/flightlog/api/routers/public.py          # unauthenticated by design, per contracts/endpoints.md
src/flightlog/core/user_seed.py              # the 5-category starter seed (research.md/data-model.md),
                                              # guarded by users.seeded_at IS NULL
src/flightlog/models/public.py               # Pydantic schemas: PublicFlightOut, PublicProfileOut —
                                              # deliberately NOT reusing FlightOut/UserOut verbatim, to
                                              # keep the public shape an explicit, reviewable allowlist
                                              # rather than "whatever the private schema happens to have"
```

### Backend (modified)
```
src/flightlog/database/models.py             # + flights.visibility, users.public_profile_enabled
src/flightlog/database/db.py                 # _run_column_migrations() guards for both
src/flightlog/api/routers/flights.py         # PUT accepts visibility
src/flightlog/api/routers/auth.py            # register() calls core/user_seed.py, sets seeded_at
src/flightlog/api/main.py                    # register the public router; wire slowapi's limiter +
                                              # exception handler (mapped to this app's own error
                                              # envelope, not slowapi's default shape)
src/flightlog/api/routers/pages.py           # + GET /public/flights/{id}, /public/profiles/{user_id}
pyproject.toml                               # + slowapi dependency
static/i18n/en.json                          # public-page + visibility-control keys
static/flight-detail.html / .js              # + visibility control
```

### Frontend (new pages)
```
static/public-flight.html    static/public-flight.js     # anonymous-visitor flight view
static/public-profile.html   static/public-profile.js    # anonymous-visitor profile view
```

### Tests (new)
```
tests/backend/test_public_routes.py    # visibility enforcement (private/unlisted/public), never-leak-
                                        # existence 404 shape, profile opt-in/opt-out, rate-limit 429
tests/backend/test_user_seed.py        # exactly-once seeding, editable afterward, no double-seed on a
                                        # second register-path call (shouldn't be possible, tested anyway)
```

## Implementation Phases

### Phase 1: Data model + starter-category seeding
The two new columns and their migration guards; `core/user_seed.py`; wiring into `auth.py`'s `register()`
exactly where its own comment already says seeding belongs. Fully testable in isolation — register a
new account, confirm exactly 5 categories exist, confirm `seeded_at` is set, confirm every category is
editable afterward via the existing `PUT /api/categories/{id}`.

### Phase 2: Flight visibility
`flights.py`'s `PUT` accepting `visibility`; validation (only the three named values). Testable without
any public-facing route yet — confirm the column round-trips correctly through the existing authenticated
API.

### Phase 3: Public surface
`api/routers/public.py`, `models/public.py`'s explicit-allowlist schemas, `slowapi` wiring (limiter,
exception handler mapped to this app's error envelope per `contracts/endpoints.md`). This is where the
never-leak-existence 404 shape and the unlisted-vs-public distinction get tested most carefully.

### Phase 4: Frontend
`public-flight.html`/`.js`, `public-profile.html`/`.js` — deliberately built without assuming any logged-
in state at all (unlike every prior page, which always calls `bootstrapPage({ requireAuth: true })`);
the visibility control added to `flight-detail.html`/`.js` for the pilot's own authenticated view.

### Phase 5: Verification pass
Live-boot walkthrough: set a flight to each of the three visibility states and confirm exactly the
expected access from an unauthenticated `curl` call at each state; confirm a private flight's public URL
and a genuinely nonexistent flight's URL produce byte-identical 404 responses; confirm rate-limiting
triggers correctly under a burst and does not affect a concurrent authenticated session; register a
brand-new account and confirm it starts with exactly 5 editable categories.
`ruff check`/`ruff format --check`/`pytest` clean. Then `sync.md`.

**Not scheduled anywhere in this task list, by design (`research.md`): the actual git-history rewrite of
`olddata/Flugbuch.xlsx`.** That remains a separate, explicitly pilot-confirmed action to perform
whenever the pilot actually decides to make the repository public — this feature only ships the
application-level readiness for that day, not the day itself.

## Dependencies

- `slowapi` 0.1.10 — new, verified current against PyPI's JSON API this session
  (`research.md`) — the first new runtime dependency since `libigc`/`simplekml` in `v0.5`.
- No new vendored JS, no new npm/build-step anything.

## Risk & Mitigations

- **Risk**: a public response schema accidentally includes a field the private `FlightOut`/`UserOut`
  schemas carry that was never meant to be public (an email address, an internal note).
  **Mitigation**: `plan.md`'s File Structure already calls for dedicated `PublicFlightOut`/
  `PublicProfileOut` schemas as an explicit allowlist, not schema reuse or inheritance from the private
  ones — reviewed field-by-field in Phase 3, not assumed safe by construction.
- **Risk**: the never-leak-existence 404 for a private flight vs. a genuinely nonexistent one drifts
  apart over time (e.g. a future edit adds a header or timing difference that lets a determined visitor
  distinguish the two).
  **Mitigation**: Phase 5's verification pass explicitly diffs the two responses byte-for-byte, not just
  "both return 404" — this is the same rigor `02-backend-conventions.md` already requires of every
  `_get_own_<x>()` helper elsewhere in the app.
- **Risk**: `slowapi`'s in-memory limiter state doesn't survive a process restart or scale across
  multiple app instances.
  **Mitigation**: acceptable for this project's actual deployment shape — one Docker container, one
  named volume, no multi-instance infrastructure exists or is planned (`architecture.md`'s Deployment
  section) — a restart resetting rate-limit counters is a minor, acceptable gap, not a real exposure.
