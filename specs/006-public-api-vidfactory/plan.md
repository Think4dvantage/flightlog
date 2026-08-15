# Implementation Plan: Public API & VidFactory Integration

Spec: [`spec.md`](./spec.md) · Research: [`research.md`](./research.md) · Data model:
[`data-model.md`](./data-model.md) · Contracts: [`contracts/`](./contracts/)

## Technical Context

Backend-first, on the existing stack — no new tech stack decisions. FastAPI + Pydantic v2 + SQLAlchemy
2.0 (two new tables, one new auth dependency pair, two new routers); one small frontend page (API key
management) following every prior feature's `bootstrapPage()`/`fetchAuth()`/i18n/dark-theme conventions.

**Architecture approach**: a second, parallel auth path (`get_api_principal`/`require_scope`) alongside
the existing JWT path (`get_current_user`) — never a replacement, never a merge of the two. This is the
one feature so far where a design doc (`02-backend-conventions.md`) already fully specifies the target
shape ahead of any code existing (`research.md`) — this plan implements that documented shape rather
than redesigning it, while flagging precisely where the documentation was ahead of, or inconsistent
with, reality.

**Performance**: NFR-001 is met by the already-decided SHA-256 + `hmac.compare_digest` verification
(`02-backend-conventions.md`) — no new performance work needed, just implementing the existing decision.

**Security**: this is the highest-stakes feature so far from a security standpoint — a leaked or over-
scoped API key is a real, direct account-access risk in a way a UI bug isn't. Every route gets the same
never-leak-existence treatment already standard in this app, applied identically across both auth paths.

## Constitution Check

| Principle (`00-ai-usage.md`) | Status |
|---|---|
| Read before acting | Done — spec, every `.ai/instructions/` file (including catching two of them being stale about what already exists, `research.md`), `architecture.md`'s `igc_segments`/API-Contracts/SQLite-Tables sections, the real `src/flightlog/` tree (not the documented-but-inaccurate one), all read before this plan was written |
| Plan before building | This document; no code has been written yet |
| Minimal scope | No generic roles/permissions system (a short enumerable scope list instead, per spec's Assumptions); no per-key usage analytics beyond `last_used_at` (P3, deferred); no rate limiting on this surface (out of scope — different threat model from `v0.9`'s public-surface limiting) |
| Tool-agnostic instructions | No `CLAUDE.md` or equivalent introduced |
| Keep docs in sync | Deferred to session end (`sync.md`); this feature's `sync.md` pass should also correct `01-project-overview.md`'s Repository Layout and `02-backend-conventions.md`'s Auth Dependencies table to describe what actually exists once implemented (`research.md`) |
| No secrets committed | N/A — and doubly relevant in-feature: the plaintext API key itself must never be logged, even at DEBUG, anywhere in this implementation |
| Prod is off-limits | N/A — local implementation; deployment follows the existing tag-push pipeline |

No violations.

## Data Model Summary

Two new tables: `api_keys` (with the `expires_at` addition `research.md` resolves) and `flight_links`.
Full detail in `data-model.md`. No column lands on an existing table; no migration guard needed beyond
`Base.metadata.create_all()`.

## File Structure

### Backend (new)
```
src/flightlog/services/apikeys.py            # mint (secrets.token_urlsafe), hash, verify — the
                                               # actual implementation of the shape 02-backend-
                                               # conventions.md already specified
src/flightlog/models/apikeys.py               # Pydantic schemas: ApiKeyOut (no secret), ApiKeyCreateOut
                                               # (includes the one-time plaintext), ApiKeyCreateIn
src/flightlog/models/integration.py           # Pydantic schemas: the frozen v1 contract's response
                                               # shapes (FlightMetadataOut, SegmentOut, FlightLinkIn)
src/flightlog/api/routers/api_keys.py         # /api/keys — JWT-authenticated
src/flightlog/api/routers/integration.py      # /api/integration/v1 — API-key-authenticated
```

### Backend (modified)
```
src/flightlog/database/models.py             # + ApiKey, FlightLink
src/flightlog/api/dependencies.py             # + ApiPrincipal, get_api_principal, require_scope()
src/flightlog/api/main.py                     # register both new routers
src/flightlog/api/routers/pages.py            # + GET /api-keys
static/i18n/en.json                           # nav + page keys
static/flight-detail.html / .js               # + linked-external-resource indicator (FR-009)
```

### Frontend (new page)
```
static/api-keys.html         static/api-keys.js   # list, create (one-time reveal), revoke
```

### New HTML route in `pages.py`
```
GET /api-keys  -> api-keys.html
```

### Tests (new)
```
tests/backend/test_api_keys.py       # mint/verify/revoke/expiry; plaintext never re-appears after
                                      # creation; revoked always wins over unexpired
tests/backend/test_integration_v1.py # scope enforcement, cross-owner 404, segment shape matches
                                      # the JWT-gated equivalent, flight-link PUT idempotency
```

## Implementation Phases

### Phase 1: Auth foundation
`services/apikeys.py` (mint/hash/verify, exact format from `02-backend-conventions.md`), the `ApiKey`/
`FlightLink` tables, `dependencies.py`'s `ApiPrincipal`/`get_api_principal`/`require_scope`. Fully
unit-testable before any route exists — verify a minted key round-trips correctly, a tampered key
fails, a revoked/expired key is rejected, all without any HTTP layer involved yet.

### Phase 2: Key management (pilot-facing)
`api/routers/api_keys.py`, `models/apikeys.py`'s schemas — the one-time-reveal creation response is the
one genuinely novel piece of behavior here (`research.md`), worth its own explicit test asserting the
plaintext never appears in any subsequent `GET`.

### Phase 3: Integration surface (API-key-facing)
`api/routers/integration.py` — flight metadata, segments (reusing `igc_segments`' shape verbatim), the
flight-link push-back with its `PUT`-idempotent semantics.

### Phase 4: Frontend
`api-keys.html`/`.js` — list, create-with-one-time-reveal, revoke-with-confirmation (NFR-003);
flight-detail's linked-resource indicator (FR-009/P2).

### Phase 5: Verification pass
Live-boot walkthrough: mint a real key, call every `/api/integration/v1` route with `curl` and an
`X-API-Key` header exactly as an external tool would (not through the browser session at all); confirm
a wrong-scope call is rejected; confirm revoking mid-session cuts off the next call immediately; confirm
the flight-link `PUT` is genuinely idempotent (call it twice with different `url`s, confirm the second
replaces rather than duplicates). `ruff check`/`ruff format --check`/`pytest` clean. Then `sync.md` —
including correcting `01-project-overview.md`/`02-backend-conventions.md`'s now-resolved stale sections
(`research.md`).

## Dependencies

- No new Python packages — `secrets`, `hashlib`, `hmac` are all stdlib.
- No new vendored JS.
- No dependency on `v0.9` — the public-surface rate limiting named there is a different threat model
  (unauthenticated traffic) from this feature's always-API-key-authenticated surface.

## Risk & Mitigations

- **Risk**: the plaintext API key accidentally ends up in a log line (e.g. a naive
  `logger.info("Created key: %s", key)` during development).
  **Mitigation**: called out explicitly in this plan's Constitution Check and should be a specific
  Phase 5 check — grep the implementation for any logging statement that touches the raw key value
  before considering this feature done.
- **Risk**: `01-project-overview.md`/`02-backend-conventions.md`'s stale sections mislead a future
  session (or a future contributor) into assuming this integration already partially exists.
  **Mitigation**: `research.md` documents the gap precisely now; Phase 5's `sync.md` pass corrects both
  files once the real implementation exists, closing the gap for good rather than leaving it stale
  indefinitely.
- **Risk**: VidFactory's own real integration turns out to need a field this contract doesn't yet
  expose, forcing a breaking change to a surface `spec.md` explicitly wants frozen.
  **Mitigation**: `spec.md`'s Success Criteria already commits to versioning (`/v1` → `/v2`) as the
  answer to this, not silently editing `/v1` — the URL already carries the version for exactly this
  reason.
