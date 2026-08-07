# Backend Conventions

## Dependency Freshness — Rule That Must Not Be Broken

**Every third-party dependency is pinned to the latest stable release at the time it is added, verified
against its registry — never copied from a sibling repo.**

"Dependency" means **all four** of these, and the rule was already broken on two of them during v0.1:

| Kind | Verify against | v0.1 miss |
|---|---|---|
| Python packages | PyPI JSON API | `pytest-asyncio` copied as `0.26.0`; actual latest was `1.4.0`, and 0.26 caps pytest below 9 — the install failed outright |
| GitHub Actions | `gh api /repos/<owner>/<repo>/releases/latest` | `actions/checkout@v4` copied from Lenticularis; actual latest was **v7**. Every action was 1–3 majors behind and CI warned about deprecated Node 20 |
| Vendored JS libraries | Upstream GitHub releases | Verified correct — Leaflet 1.9.4, Chart.js 4.5.1 |
| Base container images | Registry / endoflife.date | Verified — `python:3.14-slim` |

Verify programmatically rather than by reading a web page; a summarised page is how the
`pytest-asyncio` version was got wrong:

```bash
python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/<pkg>/json'))['info']['version'])"
gh api /repos/<owner>/<repo>/releases/latest --jq .tag_name
```

Lenticularis and VidFactory carry pins that were current when written and have since drifted. Copying
them silently starts this project on old software. Re-verify at the start of each milestone.

When a dependency turns out to be stale or unmaintained, say so and propose the replacement rather than
inheriting it. Two such replacements are already baked in — see `01-project-overview.md`.

---

## New API Router

Create `src/flightlog/api/routers/<domain>.py`, register it in `main.py`.

```python
# src/flightlog/api/routers/gliders.py
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gliders", tags=["gliders"])


def _get_own_glider(glider_id: str, current_user: User, db: Session) -> Glider:
    """
    404 whether the row is missing or simply not yours — never a 403 here.

    A 403 would confirm the id exists and belongs to someone else, which is the same
    existence-leak class of bug `04-constraints.md` calls out for the buddy-link endpoint.
    See `06-testing-conventions.md`'s coverage table: "another user's row -> 404, never
    403-with-existence-leak." Every router has one of these helpers.
    """
    row = db.get(Glider, glider_id)
    if row is None or row.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Glider not found")
    return row


@router.get("", response_model=list[GliderOut])
def list_gliders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(Glider).where(Glider.owner_id == current_user.id).order_by(Glider.sort_order)
    ).scalars().all()
```

```python
# main.py
from flightlog.api.routers import gliders as gliders_router
app.include_router(gliders_router.router)
```

**HTML page routes live in `routers/pages.py` only** — never in `main.py`, never in a domain router.
They use `include_in_schema=False` and return `FileResponse`.

**`owner_id` is never accepted from a request body.** It always comes from `current_user.id`.

---

## New SQLite Table & Migrations

**No Alembic. No `.sql` files. No `_migrations` table.**

> The blueprint ships two contradictory migration doctrines — a `.sql` + `_migrations` runner in an
> earlier revision of this file, and `_run_column_migrations()` in `04-constraints.md`. **This project
> uses `_run_column_migrations()` exclusively.** If a blueprint sync reintroduces the `.sql` runner,
> delete it again.

### 1. Define the ORM model

`database/models.py` is the single source of truth for the schema.

```python
class Glider(Base):
    __tablename__ = "gliders"
    id       = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    brand    = Column(String, nullable=False)
```

### 2. New tables need no migration

`Base.metadata.create_all(bind=engine)` runs on every startup and is idempotent — it creates only
missing tables. That is the whole story for a new table.

### 3. New columns on an existing table need an idempotent guard

```python
def _run_column_migrations(engine) -> None:
    """Add columns introduced after a table's initial schema. Safe to re-run."""
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(flights)")).fetchall()}
        if "rating" not in cols:
            conn.execute(text("ALTER TABLE flights ADD COLUMN rating INTEGER"))
            conn.commit()
            logger.info("Migration: added flights.rating column")
```

### 4. Foreign keys are NOT enforced

`PRAGMA foreign_keys=ON` is never set. `ondelete="CASCADE"` on a `ForeignKey` is **documentation**;
`cascade="all, delete-orphan"` on the ORM relationship is what actually deletes children. Write both,
but rely on the relationship.

### 5. SQLite WAL

Register a connect-time pragma listener in `init_db()`:

```python
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()
```

### 6. Seeding

A Python list plus an existence check, called from `init_db()`. Never a `.sql` fixture.

```python
def _seed_regions(engine) -> None:
    with Session(engine) as db:
        for name, order in _REGIONS:
            if db.execute(select(Region).where(Region.name == name)).first():
                continue
            db.add(Region(name=name, sort_order=order))
            logger.info("Seeded region: %s", name)
        db.commit()
```

Per-user seeding (default flight categories) is **not** a startup seeder — it runs from the
register/admin-create path and is guarded by `users.seeded_at IS NULL`.

---

## Auth Dependencies

Import from `flightlog.api.dependencies`:

| Dependency | Who passes |
|---|---|
| `get_current_user` | Valid JWT **and** `is_active` — 401 otherwise |
| `get_current_user_optional` | Same resolution, returns `None` instead of raising. **Does not check `is_active`** — never guard anything needing a live account with it |
| `require_admin` | `role == "admin"` — 403 otherwise |
| `get_api_principal` | Valid, unrevoked, unexpired API key → `ApiPrincipal(user, key, scopes)` |
| `require_scope("flights:read")` | Factory; resolves the principal then checks the scope — 403 otherwise |

**There is no global auth middleware.** Auth is a per-endpoint `Depends(...)`, which means *the absence
of a dependency is what makes a route public*. Any public route must be isolated in its own router and
documented as such at the top of the file.

Object-level authorization happens inside the handler via `_get_own_<x>()`. Row scoping is
`.where(Model.owner_id == current_user.id)`.

---

## API Keys — hash with SHA-256, not bcrypt

Format `flg_<prefix:8>_<secret:43>` from `secrets.token_urlsafe(32)`. Look up by the indexed unique
`key_prefix`, then compare with `hmac.compare_digest`.

The secret is 256 bits of CSPRNG output, not a guessable password. bcrypt's whole value is slowing
offline brute force of low-entropy secrets, which does not apply — and at ~80 ms per verification it
would cost seconds across a single VidFactory import run. **bcrypt stays for user passwords.**

---

## Config

Add new keys to the Pydantic models in `config.py` **and** to `config.yml.example`.

**Never read `os.environ` directly** — always `get_config()`. Log the resolved value of every non-secret
key at INFO on startup. A missing required key is CRITICAL + fail fast, never a silent default.

---

## Error Responses

Every error leaves as the typed envelope. See `07-api-conventions.md` for the full vocabulary.

```json
{ "error": { "code": "ENTITY_NOT_FOUND", "message": "...", "details": {} } }
```

Raising a plain `HTTPException` is fine — the registered handler maps its status to a code. Use
`AppException` when you need to set the code explicitly.

---

## Coding Standards

- **Always use type hints** on function signatures.
- **Async/await for I/O.** Note that `get_db` and the auth dependencies are **sync** (`def`) — FastAPI
  runs those in a worker threadpool, which is why `StaticPool` is mandatory in tests. See
  `06-testing-conventions.md`.
- **Pydantic v2** for all schemas and config.
- **SQLAlchemy 2.0 style** — `select()`, `.scalars().all()`, never legacy `query()`.
- **One router per domain.** All HTML page routes in `pages.py`.
- **Log extensively** — startup sequence, every request, every job. See `08-operability.md`.
- **No print statements** — always `logging`.
- **`%s`-style lazy logging** with IDs: `logger.info("Flight created: %s by %s", f.id, user.id)`.
