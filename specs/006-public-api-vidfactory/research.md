# Research: Public API & VidFactory Integration

## Decision: this feature builds what the blueprint docs describe, but two of those docs are stale about what already exists — verified against the real repo, not assumed

- **Finding**: `01-project-overview.md`'s "Repository Layout" section and `02-backend-conventions.md`'s
  "Auth Dependencies" table both describe `get_api_principal`, `require_scope`, `services/apikeys.py`,
  and `ApiPrincipal` as though already implemented. **None of them exist yet** — confirmed by reading
  the real `src/flightlog/api/dependencies.py` directly (only `get_current_user`,
  `get_current_user_optional`, `require_admin`, `client_ip`) and the real `src/flightlog/` tree (no
  `services/apikeys.py`, no `core/xcontest.py`, no `core/igc_match.py`/`igc_store.py`/`sites.py` — the
  real modules are named `igc.py`/`igc_storage.py`/`site_backfill.py`, and IGC-to-flight matching lives
  inline in `api/routers/igc.py`, not a separate module). These two files are evidently written from the
  blueprint's generic, aspirational project template at `v0.1` and never fully reconciled against what
  was actually built in later milestones.
- **Decision**: treat `02-backend-conventions.md`'s documented *shape* (`ApiPrincipal(user, key,
  scopes)`, `get_api_principal`, `require_scope("scope:name")` as a factory) as the target design —
  it's a reasonable, already-thought-through shape worth building to — but build it as genuinely new
  code in `dependencies.py`, not as "wiring up something that's already there." `sync.md` at the end of
  this feature should also correct these two files to describe reality once this ships, the same way
  this session already corrected several stale roadmap version numbers elsewhere.
- **Rationale**: This is exactly the kind of gap this session has caught twice already (the XContest
  schema, `libigc`'s real API shape) — a design doc is not proof something exists; the real source tree
  is. Worth stating explicitly here since a future implementer skimming `02-backend-conventions.md`
  alone would reasonably assume this dependency already exists and go looking for it.

## Decision: add a nullable `expires_at` to `api_keys` — resolves a real, previously-unnoticed doc inconsistency

- **Decision**: `api_keys.expires_at` (`UtcDateTime`, nullable). `NULL` means the key never expires.
  `get_api_principal` rejects a key whose `expires_at` is in the past, in addition to checking
  `revoked_at IS NULL`.
- **Rationale**: `02-backend-conventions.md`'s Auth Dependencies table explicitly says
  `get_api_principal` resolves "a valid, unrevoked, **unexpired**" key — but `architecture.md`'s
  `api_keys` column list has no expiry field at all, only `revoked_at`. One of the two documents is
  incomplete; adding the column is what makes the dependency's own documented behavior actually
  implementable, and costs nothing for a pilot who never sets one (`NULL`, no behavior change from a
  key that "never expires").
- **Alternatives considered**: Treat "unexpired" in the dependency doc as loose language for "not
  revoked" and skip the column entirely. Rejected — silently reading past a specific, deliberate-
  sounding word ("unexpired") in an existing design doc is exactly the kind of guess this session's
  research has avoided everywhere else; adding one nullable column is cheap insurance against having
  guessed wrong.

## Decision: `X-API-Key` header format and verification reuse the already-decided shape exactly

- **Decision**: `flg_<prefix:8>_<secret:43>`, minted via `secrets.token_urlsafe(32)`
  (`02-backend-conventions.md`, already decided, not revisited here). Lookup by the indexed unique
  `key_prefix`, then `hmac.compare_digest` against the SHA-256 hash of the full key. `last_used_at` is
  updated on every successful verification (best-effort, not required to be perfectly synchronous with
  the actual request it authenticates).
- **Rationale**: This exact format and hashing choice, along with its stated reasoning (256 bits of
  CSPRNG output doesn't need bcrypt's slow-hash property; SHA-256 keeps a bulk integration request fast),
  is already fully decided in `02-backend-conventions.md` — this feature implements it, it doesn't
  redesign it.

## Decision: the key value is shown exactly once, with no retrieval path afterward — a genuinely new UI pattern for this app

- **Decision**: `POST /api/keys` returns the full plaintext key in its response body, once. No other
  endpoint, ever, returns it again — matching how `services/auth.py`'s bcrypt hashes and the JWT secret
  already work (the plaintext exists transiently, never persisted, never re-derivable). The
  key-management UI must present this response in a way that visually signals "this is your only chance
  to copy this" (a distinct, non-dismissible-by-accident confirmation state), since nothing else in the
  app has needed this pattern before — every existing credential (password, JWT) is either entered by
  the user themselves or never displayed at all.
- **Rationale**: This is the correct security shape (an API key, unlike a password, must never be
  server-side-recoverable even in hashed-but-reversible form), and matches `key_hash` in `architecture.md`'s
  already-named column list — `key_hash`, not `key_ciphertext` or anything reversible.

## Decision: a duplicate flight-link push-back (same flight, same kind, same external id) replaces, not rejects or silently duplicates

- **Decision**: `PUT /api/flights/{id}/links/{kind}/{external_id}` (matching `01-project-overview.md`'s
  already-sketched route shape, `PUT .../links/video/{project_id}`) is idempotent by construction — a
  `PUT` to the same `(flight_id, kind, external_id)` tuple updates the existing row's `url`/`label`
  rather than creating a second one or erroring.
- **Rationale**: `spec.md`'s Edge Cases deliberately left this open as a planning-time decision. A `PUT`
  (not `POST`) to a fully-identified resource path is this app's own existing convention for "create or
  replace" (`specs/003-igc-ingest-analysis`'s `POST /api/flights/{id}/igc` used `POST` for its create-
  or-replace instead, but that's a file-upload endpoint where the resource identity isn't in the URL the
  same way; here the URL already fully names the resource being written, which is exactly what `PUT`
  means). VidFactory re-pushing the same project's link after re-rendering a video should update the
  existing link, not accumulate duplicates a pilot would see repeated on their flight page.
- **Alternatives considered**: Reject a duplicate with `409 CONFLICT`, forcing an explicit delete-then-
  recreate. Rejected as needless friction for the integration's own retry/re-render behavior, which is a
  completely reasonable, expected case, not an error condition.

## Decision: `/api/integration/v1`'s segment data reuses `igc_segments`' already-committed shape verbatim

- **Decision**: the highlight-timing endpoint returns the same fields `architecture.md`'s
  `igc_segments` section already commits to for exactly this consumer: `kind`, `start_offset_s`
  (seconds since takeoff — "the load-bearing field"), `start_at` (absolute time, for a camera that
  started rolling before takeoff), `duration_s`, `alt_change_m`, `vertical_velocity_ms`, `glide_ratio`.
- **Rationale**: This was designed for VidFactory's consumption specifically, back when `igc_segments`
  itself was built (`specs/003-igc-ingest-analysis`) — there is nothing to redesign here, only to expose
  under the versioned, scope-gated integration surface instead of (or in addition to) the JWT-gated
  `GET /api/flights/{id}/igc/segments` endpoint that already serves the pilot's own browser session.
