# Feature: Public API & VidFactory Integration

## Overview

Turns this project's own stated differentiator — "the API is the product, not a byproduct"
(`01-project-overview.md`) — into something a second real application can actually depend on. A pilot
can mint a scoped API key from their own account; an external tool (VidFactory today, anything else
later) uses it to read flight metadata and thermal-based highlight timing, and to push a link back to a
video it produced. VidFactory retires its own copy of this pilot's flight data once this ships.

## Clarifications

### Session 2026-08-15
- Q: `02-backend-conventions.md`'s Auth Dependencies table documents `get_api_principal` as resolving
  "a valid, unrevoked, **unexpired**" key, but the `api_keys` table's own documented columns
  (`architecture.md`) have no expiry field at all — only `revoked_at`. Which is right? → A: Neither
  was wrong so much as incomplete — add a nullable `expires_at` to `api_keys` so "unexpired" is
  actually meaningful (`NULL` = never expires, matching a long-lived service integration's needs;
  set only if the pilot wants extra safety on a given key). `revoked_at` remains the immediate-kill
  switch; `expires_at` is a self-service, optional safety net on top of it.
- Q: Should this feature migrate VidFactory's existing copy of this pilot's flight data into
  `flightlog`? → A: No — `architecture.md` already states this explicitly ("this service already holds
  the authoritative 600 flights. VidFactory's copy is discarded, not reconciled."). This feature is a
  forward-looking integration point only.

## User Stories

### P1 — Must Have

**As a pilot, I want to create and revoke scoped API keys from my own account so I can grant a specific
tool exactly the access it needs, and cut it off instantly if I change my mind.**

Acceptance Criteria:
- The pilot can create a named API key, choosing which scopes it grants (e.g. read-only flight access,
  or flight-link push-back).
- The full key value is shown exactly once, at creation time, and never again — matching how every
  other secret-bearing credential in this app already behaves (the JWT secret, bcrypt hashes: the
  plaintext is never retrievable after the fact).
- The pilot can revoke a key immediately; a revoked key stops working on its very next request.
- The pilot can optionally set an expiry date on a key at creation time; an expired key stops working
  automatically, with no manual action needed.
- The pilot can see a list of their own keys (name, scopes, created date, last-used date, revoked/expiry
  status) without ever seeing a live key value again.

**As an external tool (VidFactory today), I want to authenticate with an API key and read a specific
pilot's flight metadata and IGC-derived highlight timing so I can build a video around a real flight
without needing that pilot's login credentials.**

Acceptance Criteria:
- A request carrying a valid, unrevoked, unexpired API key with the right scope receives flight
  metadata (date, sites, duration, distance, gear, category) for flights the key's owner actually owns.
- The same surface returns IGC-derived segment data (thermals, glides, and their offsets) for a flight
  that has an uploaded track, in the exact shape `architecture.md`'s `igc_segments` section already
  commits to for this exact purpose: `start_offset_s` (seconds since takeoff) is the field an external
  video tool actually needs, never a video-relative offset this service has no way to know.
- A request with an invalid, revoked, expired, or wrong-scope key is rejected before it can read
  anything — the same "never leak whether something exists" discipline every other part of this app
  already holds itself to (a wrong-scope request gets a permission error, never a hint about what *would*
  have been returned with the right scope).
- This surface is versioned and explicitly frozen — a breaking change to its shape is a new version, not
  a silent edit to what integrators already depend on.

**As an external tool, I want to push a link back to a video I produced from a pilot's flight so the
pilot can find and watch it from their own flight log.**

Acceptance Criteria:
- The tool can attach a link (a kind/label/external id/URL) to a specific flight it was given read
  access to, using the same API key.
- The pilot sees this link on the flight's own detail page without any action of their own.
- The URL is validated server-side before it's ever stored or ever shown to the pilot, per this project's
  existing rule for any stored external link.

### P2 — Should Have

**As a pilot, I want to see which of my flights already have a linked video so I know at a glance which
ones VidFactory (or any other integrated tool) has already touched.**

Acceptance Criteria: the existing `/flights` list and flight-detail page show a visible indicator when
a flight has one or more linked external resources, without needing to open each flight individually.

### P3 — Nice to Have

**As a pilot, I want per-key usage visibility (request counts, last few endpoints hit) so I can sanity-
check what an integration is actually doing with the access I granted it.**

Acceptance Criteria: out of scope for this feature — `last_used_at` (P1) is the only usage signal this
milestone commits to; anything richer is a fast-follow, not blocking.

## Functional Requirements

- FR-001: The system MUST let a pilot create a named, scoped API key from their own account, showing
  the full key value exactly once.
- FR-002: The system MUST let a pilot revoke their own API key, effective immediately on the next
  request.
- FR-003: The system MUST let a pilot optionally set an expiry on a key at creation time; an expired
  key MUST be rejected automatically without requiring the pilot to revoke it by hand.
- FR-004: The system MUST let a pilot list their own API keys (name, scopes, created/last-used dates,
  revoked/expiry status) without ever displaying a live key value again after creation.
- FR-005: The system MUST authenticate an external request via an `X-API-Key` header, resolving it to
  the key's owning pilot and granted scopes, rejecting an invalid/revoked/expired key before any data
  is read.
- FR-006: The system MUST expose a versioned, frozen integration surface returning flight metadata and
  IGC-derived segment/highlight-timing data for flights owned by the authenticated key's pilot,
  gated by scope.
- FR-007: The system MUST let an appropriately-scoped API key attach an external link (video or
  otherwise) to a flight it can already read.
- FR-008: A stored external link's URL MUST be validated server-side (`http://`/`https://` only) before
  being persisted or displayed.
- FR-009: A pilot's own flight views MUST show any linked external resources without requiring the pilot
  to take any action to surface them.
- FR-010: Every rejection (invalid, revoked, expired, wrong-scope) MUST behave identically from the
  caller's point of view where "identically" matters for security — a wrong-scope request must not leak
  what a correctly-scoped one would have returned.
- FR-011: All user-visible chrome for the key-management UI MUST go through the existing translation
  mechanism.
- FR-012: The key-management UI MUST use the existing dark theme and navigation shell.

## Non-Functional Requirements

- NFR-001: API-key verification must not meaningfully slow a bulk integration request — the existing
  design decision to hash with SHA-256 rather than bcrypt (`02-backend-conventions.md`) already exists
  specifically for this reason; this feature implements that decision, it doesn't need to make it fresh.
- NFR-002: The key-management UI must be usable by keyboard alone.
- NFR-003: Creating a key that grants broad scope, and revoking a key, are both consequential actions —
  the UI must make the granted scopes clearly visible before creation, and revocation must not be a
  single accidental click without confirmation.

## Success Criteria

- VidFactory (or any comparably-scoped external tool) can be pointed at this service using only a
  self-service-generated API key — no manual, out-of-band credential provisioning.
- A pilot can grant, inspect, and revoke machine access to their own account entirely through the UI,
  the same way they already manage every other credential-adjacent setting in this app.
- The `/api/integration/v1` surface never changes shape for an existing scope without a version bump —
  matching `architecture.md`'s "frozen contract" framing for this exact endpoint.
- Revoking a key immediately and completely cuts off the tool that was using it, with no propagation
  delay and no residual access through any cached credential.

## Key Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| API Key | owner, name, key prefix (shown), key hash (never shown), granted scopes, created/last-used/expires/revoked timestamps | The plaintext secret exists only once, in the creation response — never stored, never re-displayable |
| Flight Link | which flight, kind (e.g. `video`), external id, URL, label | Populated by an external tool's push-back (FR-007); shown on the pilot's own flight views (FR-009) |

## Out of Scope

- Any UI or API for VidFactory's own side of the integration (this spec only covers this service's
  surface).
- Migrating VidFactory's existing copy of this pilot's data into `flightlog` (see Clarifications — it is
  discarded, not reconciled).
- Per-key usage analytics beyond `last_used_at` (P3, deferred).
- Rate limiting on this surface specifically — the public-surface rate limiting named in `features.md`'s
  `v0.9` entry covers the *public*, unauthenticated surface; this feature's surface is always API-key
  authenticated, a different threat model, and is not blocked on `v0.9`.
- A public, unauthenticated flight feed (`01-project-overview.md` mentions this as a future consumer of
  the same general API-first philosophy, not a deliverable of this specific milestone).

## Assumptions

- There is exactly one pilot account in the system today (matches every prior feature's assumption) —
  this feature's scoping model is designed to be correct for multiple pilots each managing their own
  keys, even though only one exists to test it against right now.
- VidFactory's own team can adapt to whatever this service's contract turns out to be — this feature is
  not blocked on VidFactory shipping its own side first, since `architecture.md` already treats this
  service as the authoritative source VidFactory must conform to, not the reverse.
- A key's scope set is small and enumerable (e.g. `flights:read`, `flight_links:write`) — this feature
  does not need a generic permissions/roles system, just a short, explicit list of named capabilities.

## Dependencies

- Requires the existing `flights` table, its computed altitude figures, and `igc_tracks`/`igc_segments`
  (v0.5) as the data this surface reads.
- Requires the existing JWT-based `get_current_user` machinery to remain the pilot-facing auth path —
  this feature adds a second, parallel machine-auth path, it does not replace or touch the first.

## Edge Cases

- A key with both an expiry and a revocation: revocation always wins immediately, regardless of the
  expiry date — there is no scenario where a revoked-but-not-yet-expired key still works.
- A key scoped only for `flights:read` attempting to call the flight-link push-back endpoint: rejected
  with a permission error, not a 404 that could be mistaken for "that flight doesn't exist."
  the same "never leak existence" principle applied consistently.
- A flight-link push-back for a flight the key's owner does not own (e.g. a stale/incorrect project id
  from the external tool's own bug): rejected the same way any other cross-owner reference already is
  in this app — not found, never a 403 that confirms the flight exists under someone else's account.
- A pilot who deletes their account (if that ever exists) or whose account is deactivated: every one of
  their API keys must stop working immediately, the same as their JWT sessions already do via
  `get_current_user`'s existing `is_active` check.
- Re-attaching the same external link (same kind + external id) to a flight that already has one: this
  feature does not specify silent dedup vs. rejection vs. replacement as a product decision — left for
  the planning phase to resolve against whatever is simplest and safest, since no user story depends on
  a specific choice here.
