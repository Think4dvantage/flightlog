# Constraints — What NOT to Do

## AI Files

**All AI-related content lives exclusively in `.ai/`.** Never create tool-specific instruction files such
as `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules`, or any equivalent —
not even as thin pointers. Instructions, context, prompts and plans all go in `.ai/` and nowhere else.

---

## Production

**Never touch prod directly.** All production changes go through the deployment pipeline. No direct SSH,
no direct `docker-compose` on the prod host.

---

## Frontend

- **Never add npm or a build step.** No bundler, no `package.json`.
- **Never reference a CDN.** CSP `script-src 'self'` blocks it in the browser. Vendor the library.
- **Always bump the version in `pyproject.toml` when static assets change** — the version is the cache key.
- **Never assign untrusted data to `innerHTML`.** Flight comments and user-supplied URLs are the risk.

---

## Secrets

**Never commit secrets.** `config.yml` and `.env` are gitignored. Only `config.yml.example` with
placeholder values is committed.

---

## Personal Data

`olddata/Flugbuch.xlsx` contains 600 flights of personal history, including free-text comments naming
friends. **Scrubbed from git history 2026-08-16 (v0.9)** via `git filter-repo --path
olddata/Flugbuch.xlsx --invert-paths` — a plain `git rm` would not have been enough, since the blob
stays reachable in every earlier commit. Every commit SHA and every tag (`v0.1.0`–`v0.9.0`) changed as
a result — a hard, irreversible rewrite, not a revertible commit. The file is `/olddata/`-gitignored
now and kept on disk **untracked** so `core/importer.py`/`core/secondary_import.py`'s default `--path`
and the real-workbook regression tests (already `skipif`-gated on the file's presence) keep working
locally — it is simply never committed again. **Never re-add it to git.**

---

## Database Migrations

**No Alembic. No `.sql` migration files. No `_migrations` table.**

New tables are created by `Base.metadata.create_all()`, which is idempotent and runs on every startup.
New columns get an idempotent `PRAGMA table_info()`-guarded `ALTER TABLE` in `_run_column_migrations()`.
Seeding is a Python list plus an existence check.

> **Known blueprint conflict.** Earlier blueprint revisions ship a `.sql` + `_migrations` runner in
> `02-backend-conventions.md` while stating the opposite here. This project uses `_run_column_migrations()`
> only. If a blueprint sync reintroduces the `.sql` runner, delete it again and leave this note in place.

---

## i18n

**Never hardcode a user-visible string in JS or HTML** without a corresponding key in all configured
locale files. **Never translate user data** — site names, categories, glider names and comments are
German source data and stay verbatim. See `03-frontend-conventions.md`.

---

## Code Quality

- Don't add features, refactor code, or make "improvements" beyond what was asked.
- Don't add error handling, fallbacks, or validation for scenarios that can't happen.
- Don't create helpers or abstractions for one-time operations.
- Don't design for hypothetical future requirements.
- Don't add docstrings, comments, or type annotations to code you didn't change.
- Don't use feature flags or backwards-compatibility shims when you can just change the code.

---

## Architecture

- No Alembic — see above.
- No print statements in production code — use `logging`.
- Never read `os.environ` directly — always `get_config()`.
- Never put routes in `main.py` — one router per domain; all HTML page routes in `pages.py`.
- Never accept `owner_id` from a request body — it comes from `current_user.id`.
- No InfluxDB, no scheduler, no collectors, no pyproj. Inherited instructions mentioning them do not apply.

---

## Dependencies

**Never copy a version pin from Lenticularis or VidFactory.** Verify the latest stable release against
the registry when adding any package, and re-verify at the start of each milestone. Those repos are
whole major versions behind on several packages.

**Do not reintroduce `python-jose`, `passlib` or `black`.** They are deliberately replaced by PyJWT,
direct `bcrypt` and `ruff format`. See `01-project-overview.md` for the reasoning.

---

## Security — Rules That Must Not Be Recur

These are the classes of bug this stack has actually shipped before. Each is cheap to avoid and
expensive to find.

### JWT must fail closed at startup

The app **must refuse to start** if `auth.jwt_secret` is empty, shorter than 32 characters, or one of
the known placeholder values. A dev placeholder reaching prod is a total auth bypass.

```python
if not secret or len(secret) < 32 or secret in _PLACEHOLDER_SECRETS:
    logger.critical("auth.jwt_secret is unset, too short, or a placeholder — refusing to start")
    raise RuntimeError("Invalid auth.jwt_secret")
```

### Always pass `algorithms=` explicitly on decode

```python
# WRONG — accepts whatever the token's header claims, including "none"
jwt.decode(token, secret)

# RIGHT
jwt.decode(token, secret, algorithms=["HS256"])
```

This is the algorithm-confusion CVE class that python-jose shipped. PyJWT makes the argument mandatory,
which is one reason it was chosen.

### Validate URL schemes server-side

Any user-supplied URL that gets stored and shown back to a pilot must be rejected unless it's
`http://` or `https://`, **in the Pydantic model**, not in the template — `javascript:`/`data:` URLs
are the attack. `flight_links.url` (v0.8, `models/integration.py`'s `FlightLinkIn.url` `field_validator`)
is the first real implementation of this rule in the codebase; follow its pattern.

Earlier revisions of this file cited `media_links.url`, `tracker_links.url`, and site `webcam_url` /
`rules_url` as though they were existing precedent for this rule. They were not: none of those columns
or tables exist anywhere in `database/models.py`, and no code ever validated a URL before v0.8. See
`architecture.md`'s SQLite Tables section — `media_links` is a real, unbuilt backlog item
(`features.md`); `tracker_links`/site `webcam_url`/`rules_url` have no plan behind them at all and are
listed under "Tables that do NOT exist."

### Never leak account existence

`POST /api/buddies/{id}/link` returns **202 regardless of whether the email belongs to a registered
user**. A 404 on an unknown address turns the endpoint into a user-enumeration oracle. The same applies
to password reset when it ships.

### A private/nonexistent row and a genuinely missing row must 404 byte-identically

`GET /api/public/flights/{id}` and `GET /api/public/profiles/{user_id}` (v0.9) are the second real
implementation of this principle, after the buddy-link rule above. A single shared raise site
(`api/routers/public.py`'s `_not_found()`), never two independently-written `AppException` calls that
could drift apart over time — a difference in message, header, or timing is exactly the signal a
determined visitor could use to enumerate private ids. A regression test for this must compare raw
response bytes (`response.content`), not parsed JSON (`response.json() ==`) — structural equality
would still pass if a future edit added a field to one branch but not the other.

### Any unauthenticated page must call `bootstrapPage({ anonymous: true })`, not just `{ requireAuth: false }`

`requireAuth: false` only skips the "redirect if logged out" check. It does **not** stop
`bootstrap.js`'s nav rendering from calling `loadCurrentUser()` → `fetchAuth('/api/auth/me')` whenever
`localStorage` happens to hold a token — and a stale/expired token's failed refresh inside `fetchAuth()`
clears storage and redirects to `/login`, which silently breaks a page a total stranger must be able to
load. `static/public-flight.js`/`public-profile.js` (v0.9) are the first pages needing this; the `{
anonymous: true }` option skips the token check and the authenticated nav links entirely, regardless of
what a visitor's browser happens to hold. Curl-based verification cannot catch this class of bug — curl
has no `localStorage` — so this needs either a real browser session or a Node harness that imports the
real `bootstrap.js` under a stubbed DOM/localStorage/fetch.

### Never interpolate user input into a query string

Use bound parameters. For any identifier that must be interpolated (a table or column name in a
`PRAGMA`), validate it against `^[\w\-]{1,64}$` at the router, before it reaches the data layer.

---

## Error Handling — Rules That Must Not Recur

### Never swallow an exception

```python
# WRONG
try:
    analyze(path)
except Exception:
    pass

# WRONG — looks responsible, still loses the failure
try:
    analyze(path)
except Exception as exc:
    logger.warning("analysis failed: %s", exc)

# RIGHT
try:
    analyze(path)
except IgcError:
    logger.exception("IGC analysis failed — path=%s", path)
    raise
```

A bare `except: pass` around IGC parsing turns a corrupt upload into a flight that silently has no
track, which is far harder to diagnose than a 422.

### The error envelope is this project's own shape

```json
{ "error": { "code": "...", "message": "...", "details": {} } }
```

It is **not** RFC 7807. Do not rename it to `type`/`title`/`detail`.

### `jsonable_encoder` in the validation handler is required, not cosmetic

Pydantic v2 puts the exception object itself into `ctx.error`. Without `jsonable_encoder`, `JSONResponse`
cannot serialise it and the handler raises a 500 while trying to report a 422.

---

## Performance — Rules That Must Not Recur

### Never block the event loop

IGC parsing is CPU-bound and takes seconds on a large track. Calling it directly from an `async def`
handler stalls every other request in the process.

```python
# WRONG
result = analyze(path)

# RIGHT
result = await asyncio.to_thread(analyze, path)
```

### Batch before looping

Fetching one row per item in a loop is the N+1 that kills the flights table and the stats page. Write a
batched query that takes a list and returns a dict keyed by id.

### Bound every module-level cache

Any module-level cache dict needs a maximum size, an eviction policy and a `threading.Lock`. An unbounded
cache keyed on user input is a memory-exhaustion bug.
