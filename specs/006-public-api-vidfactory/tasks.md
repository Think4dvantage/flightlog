# Tasks: Public API & VidFactory Integration

Spec: [`spec.md`](./spec.md) · Plan: [`plan.md`](./plan.md) · Data model: [`data-model.md`](./data-model.md)
· Contracts: [`contracts/endpoints.md`](./contracts/endpoints.md) · Research: [`research.md`](./research.md)

## Summary

- Total tasks: 21
- Parallel opportunities: 6 (marked `[P]`)
- MVP scope: Phase 3 (US1 — create/list/revoke keys) is the smallest independently-shippable slice; the
  integration surface (Phase 4/5) is what actually delivers this milestone's stated purpose, so treat
  Phase 3 as necessary-but-not-sufficient for "done," not a natural stopping point.

Test tasks included throughout, matching every prior feature's precedent.

## Dependencies

```
Phase 1 (Setup) ─> Phase 2 (Foundation: 2 tables, apikeys service, auth dependencies) ─┬─> Phase 3  US1 key management (pilot-facing)
                                                                                          │        │
                                                                                          │        v
                                                                                          └─> Phase 4  US2 integration surface (API-key-facing)
                                                                                                   │
                                                                                                   v
                                                                                              Phase 5  US3 flight-link push-back + pilot-facing indicator

Final Phase — Polish
```

Phase 4 needs Phase 2's auth dependencies but not Phase 3's routes — it can proceed in parallel with
Phase 3 if convenient. Phase 5 needs Phase 4's routes to exist (the push-back endpoint lives in the same
router).

---

## Phase 1 — Setup

- [x] T001 Confirm `research.md`'s finding still holds — re-check `src/flightlog/api/dependencies.py`
      and the real module tree for `get_api_principal`/`require_scope`/`services/apikeys.py` in case a
      later, unrelated change already introduced something with the same name

## Phase 2 — Foundation

- [x] T002 [P] Add `ApiKey`, `FlightLink` ORM models to `src/flightlog/database/models.py` per
      `data-model.md` (including the `expires_at` addition)
- [x] T003 Create `src/flightlog/services/apikeys.py` — mint (`flg_<prefix:8>_<secret:43>` via
      `secrets.token_urlsafe(32)`), hash (SHA-256), verify (`hmac.compare_digest` against `key_hash`
      looked up by `key_prefix`)
- [x] T004 [P] `tests/backend/test_api_keys.py` (service-level, no HTTP yet) — mint/verify round-trip, a
      tampered key fails, a revoked key fails regardless of expiry, an expired-but-not-revoked key fails
- [x] T005 Add `ApiPrincipal`, `get_api_principal`, `require_scope(...)` to
      `src/flightlog/api/dependencies.py` — the actual implementation of the shape
      `02-backend-conventions.md` already specified (`research.md`)
- [x] T006 [P] Create `src/flightlog/models/apikeys.py` — `ApiKeyOut` (no secret), `ApiKeyCreateOut`
      (includes the one-time plaintext), `ApiKeyCreateIn`

## Phase 3 — Create, list, and revoke API keys [US1]

**Goal**: a pilot can mint a scoped key, see their own keys without ever seeing a live value again, and
revoke one immediately.
**Independent test criteria**: creating a key returns the plaintext once; a subsequent list call never
shows it; revoking a key makes `get_api_principal` reject it on the very next simulated request; an
optional expiry rejects the key automatically once passed, with no revoke action taken.

- [x] T007 [US1] Create `src/flightlog/api/routers/api_keys.py` — `GET`/`POST /api/keys`,
      `POST /api/keys/{id}/revoke`, `DELETE /api/keys/{id}`, per `contracts/endpoints.md`; register in
      `src/flightlog/api/main.py`
- [x] T008 [US1] [P] `tests/backend/test_api_keys.py` (HTTP-level) — create shows plaintext once, list
      never does, revoke takes effect immediately, expiry auto-rejects, cross-owner 404
- [x] T009 [US1] Create `static/api-keys.html`/`.js` — list, create form with scope selection, the
      one-time-reveal confirmation state (`research.md`), revoke with confirmation (NFR-003)
- [x] T010 [US1] Add `GET /api-keys` route to `src/flightlog/api/routers/pages.py`; nav entry in
      `static/bootstrap.js`
- [x] T011 [US1] [P] Add `api_keys.*` i18n keys, including explicit "copy this now, you won't see it
      again" copy for the one-time reveal, to `static/i18n/en.json`

## Phase 4 — Integration surface: flight metadata and IGC segments [US2]

**Goal**: an API-key-authenticated request can read a flight's metadata and IGC-derived segment/
highlight-timing data, correctly scoped and rejected when it shouldn't succeed.
**Independent test criteria**: a correctly-scoped key reads a flight it owns; a wrong-scope key gets
403, never a hint of what it would have seen; a key requesting another owner's flight gets 404; segment
response fields match the JWT-gated equivalent's shape exactly.

- [x] T012 [US2] Create `src/flightlog/models/integration.py` — `FlightMetadataOut`, `SegmentOut`
      schemas
- [x] T013 [US2] Create `src/flightlog/api/routers/integration.py` with
      `GET /api/integration/v1/flights/{id}` and `.../segments`, gated by `require_scope("flights:read")`;
      register in `main.py`
- [x] T014 [US2] [P] `tests/backend/test_integration_v1.py` — correct-scope read, wrong-scope 403,
      cross-owner 404, segment shape parity with `GET /api/flights/{id}/igc/segments`

## Phase 5 — Flight-link push-back and pilot-facing indicator [US3]

**Goal**: an appropriately-scoped key can attach an external link to a flight, idempotently, and the
pilot sees it without any action of their own.
**Independent test criteria**: a `PUT` creates a link; a second `PUT` to the same
`(flight, kind, external_id)` replaces rather than duplicates; the pilot's flight-detail page shows the
linked resource; an invalid URL scheme is rejected before storage.

- [x] T015 [US3] Add `PUT /api/integration/v1/flights/{id}/links/{kind}/{external_id}` to
      `integration.py`, gated by `require_scope("flight_links:write")`; idempotent create-or-replace on
      the `UniqueConstraint(flight_id, kind, external_id)` (`research.md`)
- [x] T016 [US3] [P] Extend `test_integration_v1.py` — create, idempotent replace, invalid-URL rejection
- [x] T017 [US3] Add a linked-external-resource indicator to `static/flight-detail.html`/`.js` (FR-009)
- [x] T018 [US3] [P] Add relevant i18n keys for the flight-detail indicator to `en.json`

## Final Phase — Polish

- [x] T019 Live-boot verification: mint a real key via the UI, call every `/api/integration/v1` route
      with `curl` and an `X-API-Key` header exactly as an external tool would (not through the browser
      session); confirm revoking mid-session cuts off the next call immediately; confirm the flight-link
      `PUT` is genuinely idempotent
- [x] T020 Grep the entire implementation for any logging statement that could touch a raw API key value
      (`plan.md`'s specific risk) — confirm none exists
- [x] T021 `ruff check`/`ruff format --check`/full `pytest` clean; bump `pyproject.toml`'s version;
      `sync.md` — update `architecture.md` (API Contracts, SQLite Tables), correct
      `01-project-overview.md`/`02-backend-conventions.md`'s now-stale sections (`research.md`),
      `features.md` (mark v0.8 shipped), `RESUME.md`
