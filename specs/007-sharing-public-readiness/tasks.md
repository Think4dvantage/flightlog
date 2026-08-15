# Tasks: Sharing & Public Readiness

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 20
- Parallel opportunities: 5 (marked `[P]`)
- MVP scope: Phase 3 (US1 — per-flight visibility + the public flight route) is the smallest
  independently-shippable slice; Phase 5's starter-category seeding is independent and P2, not
  blocking.

Test tasks included throughout, matching every prior feature's precedent. **The git-history scrub is
deliberately not a task in this list** (`research.md`/`plan.md`) — it is a separate, explicitly
pilot-confirmed operational step, never automated as part of implementing this feature.

## Dependencies

```
Phase 1 (Setup: verify slowapi still current) ─> Phase 2 (Foundation: 2 new columns + migrations) ─┬─> Phase 3  US1 flight visibility + public flight route
                                                                                                       │        │
                                                                                                       │        v
                                                                                                       ├─> Phase 4  US1 public profile route (needs Phase 3's never-leak-existence pattern established)
                                                                                                       │
                                                                                                       └─> Phase 5  US2 self-registration starter-category seeding (fully independent)

Final Phase — Polish
```

Phase 5 depends only on Phase 2 and can proceed in parallel with Phases 3/4.

---

## Phase 1 — Setup

- [ ] T001 Re-verify `slowapi` is still the current version (`pypi.org/pypi/slowapi/json`) if
      implementation starts a meaningful time after this plan

## Phase 2 — Foundation

- [ ] T002 [P] Add `flights.visibility` and `users.public_profile_enabled` columns with idempotent
      `_run_column_migrations()` guards in `src/flightlog/database/db.py`
- [ ] T003 Add `slowapi` to `pyproject.toml`; wire its limiter and an exception handler mapped to this
      app's own error envelope (not `slowapi`'s default shape) in `src/flightlog/api/main.py`

## Phase 3 — Per-flight visibility and the public flight route [US1]

**Goal**: a pilot can set a flight's visibility; an anonymous visitor can view an unlisted or public
flight by its exact URL, and gets a byte-identical 404 for a private or nonexistent flight.
**Independent test criteria**: three visibility states round-trip correctly through the authenticated
`PUT`; an unauthenticated `GET` succeeds for unlisted/public and 404s identically for private vs.
genuinely-missing; changing visibility takes effect on the very next request, no delay.

- [ ] T004 [US1] Extend `src/flightlog/api/routers/flights.py`'s `PUT` to accept and validate
      `visibility` (`private`\|`unlisted`\|`public` only)
- [ ] T005 [US1] Create `src/flightlog/models/public.py` — `PublicFlightOut` as an explicit field
      allowlist (`plan.md`'s specific risk note), not inherited from `FlightOut`
- [ ] T006 [US1] Create `src/flightlog/api/routers/public.py` (unauthenticated by design, documented as
      such at the top of the file, per `research.md`) with `GET /api/public/flights/{id}`; register in
      `src/flightlog/api/main.py`
- [ ] T007 [US1] [P] `tests/backend/test_public_routes.py` — visibility enforcement for all three
      states; byte-for-byte identical 404 response for a private flight vs. a nonexistent id
- [ ] T008 [US1] Create `static/public-flight.html`/`.js` — no `requireAuth`, no assumption of a logged-
      in session at all
- [ ] T009 [US1] Add `GET /public/flights/{id}` to `src/flightlog/api/routers/pages.py`
- [ ] T010 [US1] [P] Add a visibility control to `static/flight-detail.html`/`.js`; NFR-003's "make the
      resulting exposure level unambiguous" copy
- [ ] T011 [US1] [P] Add relevant i18n keys to `static/i18n/en.json`

## Phase 4 — Public profile [US1, continued]

**Goal**: a pilot can opt in to a public profile listing their public flights; an anonymous visitor sees
exactly that, never more, never a hint about an opted-out or nonexistent profile being different.
**Independent test criteria**: an opted-in profile shows only `public`-visibility flights, never
`unlisted` ones; opting out immediately removes access; a disabled and a nonexistent profile 404
identically.

- [ ] T012 [US1] Add `PUT /api/users/me` (or extend whatever existing "my account" route already covers
      profile-adjacent settings) to accept `public_profile_enabled`
- [ ] T013 [US1] Add `PublicProfileOut` to `models/public.py`; add `GET /api/public/profiles/{user_id}`
      to `public.py`
- [ ] T014 [US1] [P] Extend `test_public_routes.py` — opt-in/opt-out, unlisted-never-listed-on-profile,
      disabled-vs-nonexistent-profile parity
- [ ] T015 [US1] Create `static/public-profile.html`/`.js`; add the opt-in/opt-out control somewhere in
      the pilot's own account settings UI
- [ ] T016 [US1] Add `GET /public/profiles/{user_id}` to `pages.py`

## Phase 5 — Self-registration starter-category seeding [US2]

**Goal**: a newly self-registered account gets 5 editable starter categories automatically, exactly
once.
**Independent test criteria**: register a new account, confirm exactly 5 categories exist with the
right names/flags; confirm `users.seeded_at` is set; confirm every seeded category is editable via the
existing `PUT /api/categories/{id}`; confirm nothing re-seeds on a second login or token refresh.

- [ ] T017 [US2] Create `src/flightlog/core/user_seed.py` — the 5-category constant
      (`data-model.md`), written through the existing category-creation path, guarded by
      `users.seeded_at IS NULL`
- [ ] T018 [US2] Wire `user_seed.py` into `src/flightlog/api/routers/auth.py`'s `register()`, exactly
      where its own existing comment already says this belongs
- [ ] T019 [US2] [P] `tests/backend/test_user_seed.py`

## Final Phase — Polish

- [ ] T020 Live-boot verification: set a flight to each visibility state and confirm exactly the
      expected unauthenticated access at each; confirm the private-vs-nonexistent 404 responses are
      byte-identical; confirm rate-limiting triggers under a burst without affecting a concurrent
      authenticated session; register a brand-new account and confirm it starts with exactly 5 editable
      categories. `ruff check`/`ruff format --check`/full `pytest` clean; bump `pyproject.toml`'s
      version; `sync.md` — update `architecture.md`, `features.md` (mark v0.9 shipped), `RESUME.md`,
      **and explicitly remind the pilot that the git-history scrub is still a separate, manually-
      confirmed step before the repository's visibility can actually change** (`research.md`)
