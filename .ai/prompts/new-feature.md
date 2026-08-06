# Prompt: Implement a New Feature

Use this prompt as a checklist when implementing any non-trivial feature end-to-end.

---

## Backend Checklist

- [ ] New SQLite table(s) → ORM model in `database/models.py`. **New tables need no migration**; new
      *columns* on an existing table need an idempotent guard in `db.py:_run_column_migrations()`
- [ ] Every user-owned table carries `owner_id`, NOT NULL and indexed
- [ ] New Pydantic schemas in `src/flightlog/models/` — `Update` fields all `Optional`, `Out` sets
      `from_attributes`
- [ ] New router at `src/flightlog/api/routers/{domain}.py` → register in `main.py`
- [ ] `_get_own_{entity}()` ownership helper — 404 if missing, 403 if not yours
- [ ] `owner_id` taken from `current_user.id`, **never** from the request body
- [ ] Auth dependency on every endpoint (see `.ai/instructions/02-backend-conventions.md`). Remember
      that the *absence* of a dependency is what makes a route public
- [ ] Any CPU-bound work (IGC parsing) wrapped in `await asyncio.to_thread(...)`
- [ ] Config keys for anything configurable → `config.py` Pydantic models **and** `config.yml.example`
- [ ] Errors leave as the typed envelope; user-supplied URLs validated for `http(s)` scheme

## Frontend Checklist

- [ ] New `.html` page in `static/`, plus a companion `.js` if the page is large
- [ ] Page route added to `routers/pages.py` (never to `main.py` or a domain router)
- [ ] Exactly one `<script type="module">` block, calling `bootstrapPage({ page: '<name>' })`
- [ ] All user-visible strings have i18n keys in every configured locale. **User data — site names,
      categories, glider names, comments — is never translated**
- [ ] Dark theme tokens: `#0f1117` body, `#1a1f2e` cards, `#2d3748` borders, `#e2e8f0` text, `#90cdf4` accent
- [ ] `fetchAuth()` used for all authenticated calls
- [ ] `shared.css` linked; no nav CSS duplicated in a page `<style>` block
- [ ] `textContent`, never `innerHTML`, for anything user-supplied
- [ ] Mobile-responsive (test at ≤640 px)
- [ ] Console logging on every new/modified function, prefixed `[FL:<page>]`
- [ ] **Version bumped in `pyproject.toml`** if any static asset changed — it is the cache key

## Tests

- [ ] Happy path + ownership scoping (another user's row → 404)
- [ ] Any new expensive dependency stubbed in `conftest.py` (see the `fake_analyzer` pattern)
- [ ] No hardcoded clock times in fixtures — build relative to `datetime.now(timezone.utc)`

## Quality

- [ ] No hardcoded config values — all through `get_config()`
- [ ] No print statements — use `logging` with `%s` lazy formatting
- [ ] Type hints on all function signatures
- [ ] No npm / build step introduced, no CDN reference added
- [ ] Every new dependency pinned to the **latest stable release**, verified against its registry

Refer to `.ai/context/architecture.md` for data models, domain algorithms and API contracts.
Refer to `.ai/context/features.md` for the roadmap and what is deliberately deferred.
