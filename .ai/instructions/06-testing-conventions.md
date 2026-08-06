# Testing Conventions

## Philosophy

Backend logic must be test-gated. Tests give AI-assisted development a safety net — they catch
regressions that static analysis misses and make refactors safe.

Most of this file documents **traps**, not the happy path. The happy path is obvious; the traps below
each cost real debugging time in a sibling project and will cost it again if they are removed during a
blueprint sync.

---

## Backend: Pytest

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"       # all async tests run automatically — no @pytest.mark.asyncio needed
testpaths = ["tests"]
```

> **Do not copy the blueprint's example test.** It uses `AsyncClient(app=app, base_url=...)`, which
> httpx removed in 0.28. The correct form is `AsyncClient(transport=ASGITransport(app=app), ...)`, as
> below. It also uses `@pytest.mark.asyncio`, which `asyncio_mode = "auto"` makes unnecessary.

### File layout

```
tests/
  __init__.py
  backend/
    __init__.py
    conftest.py               # shared fixtures
    test_auth.py
    test_health.py
    test_errors.py
    test_static_caching.py
    test_igc_analysis.py      # the ONLY module that runs the real analyzer
  fixtures/
    igc/*.igc                 # small real tracks, committed, `-text` in .gitattributes
```

---

## conftest.py — the core harness

Four concerns: config isolation, DB isolation, app wiring, expensive-work stubbing.

### 1. Config isolation (`autouse=True`)

```python
import flightlog.config as _fl_config
from flightlog.config import MainConfig, DatabaseConfig, AuthConfig, LoggingConfig, APIConfig

_JWT_SECRET = "test-secret-that-is-at-least-32-chars!!"
_TEST_CONFIG = MainConfig(
    database=DatabaseConfig(path=":memory:"),
    auth=AuthConfig(jwt_secret=_JWT_SECRET, allow_self_registration=True),
    logging=LoggingConfig(level="warning", file=""),
    api=APIConfig(),
)

@pytest.fixture(autouse=True)
def _patch_config(monkeypatch):
    monkeypatch.setattr(_fl_config, "_config", _TEST_CONFIG)
```

`get_config()` checks the module-level `_config` first, so setting it directly bypasses all file I/O at
every call site.

Note `allow_self_registration=True` in the test config. Production defaults to `False`; the registration
tests need it on, and a separate test flips it off and asserts the 403.

### 2. In-memory SQLite engine

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from flightlog.database.models import Base

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
```

**`poolclass=StaticPool` is mandatory, not cosmetic.** An in-memory SQLite engine defaults to
`SingletonThreadPool`, which opens one connection *per thread* — and every in-memory SQLite connection
is its own separate, empty database. FastAPI runs **sync** dependencies (`get_db`, `get_current_user`,
`require_admin` — all `def`, not `async def`) in a worker threadpool, so they land on a different thread
and see none of the tables `create_all()` built on the main thread, failing with `no such table: users`.

Confusingly, `async def` handlers work fine, because their body runs on the event loop thread — so the
bug only surfaces on endpoints that authenticate, which makes it look arbitrary. `StaticPool` shares the
one connection across all threads.

### 3. FastAPI test app

```python
from contextlib import asynccontextmanager
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from flightlog.api.main import create_app
from flightlog.database.db import get_db

@pytest_asyncio.fixture
async def test_app(db_engine, tmp_path):
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    @asynccontextmanager
    async def _test_lifespan(app):
        yield

    app = create_app()
    app.router.lifespan_context = _test_lifespan

    # Set app.state DIRECTLY — see the warning below.
    app.state.igc_root = tmp_path / "igc"
    app.state.igc_root.mkdir()

    def _get_test_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield app

@pytest_asyncio.fixture
async def client(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac
```

**Set `app.state` directly in the fixture. Do not set it from inside `_test_lifespan`** — httpx's
`ASGITransport` never emits ASGI lifespan events, so **no `lifespan_context` ever runs under it**. State
assigned there is silently never applied, and every route that reads it fails with a confusing 500 or
503. Routes that 404 earlier on some other lookup still pass, which makes the failure look arbitrary.

Replacing `app.router.lifespan_context` with a no-op is still worth doing: it guarantees the real
lifespan (DB init, JWT validation, seeding) cannot fire if a test ever *does* drive the lifespan, e.g.
via `asgi-lifespan`'s `LifespanManager`.

### 4. Stub the IGC analyzer for every API test

IGC parsing is slow, CPU-bound and touches the filesystem. **No API test may run the real analyzer.**

```python
_FAKE_ANALYSIS = {
    "takeoff_at": ..., "landing_at": ..., "duration_s": 3600,
    "alt_source": "baro", "max_alt_m": 2500,
    "thermal_count": 3, "total_climb_m": 900, "best_climb_ms": 2.4,
    "glide_count": 4, "total_glide_km": 18.2, "glide_ratio": 7.1,
    "segments": [],
}

@pytest.fixture(autouse=True)
def fake_analyzer(monkeypatch):
    monkeypatch.setattr("flightlog.core.igc.analyze", lambda path: dict(_FAKE_ANALYSIS))
```

This plays the role a backend stub plays elsewhere, and it has the same failure mode: **when the
analyzer grows a new output key, add it here too.** A missing key surfaces as a `KeyError` inside a
route and reads as an unrelated 500.

The real analyzer is exercised in exactly one module, `test_igc_analysis.py`, via a non-autouse
`real_igc` fixture pointing at `tests/fixtures/igc/`. That module asserts known-good numbers and is
where the thermal-filter regression is pinned (see below).

---

## Writing tests

### API tests — use the `client` fixture

Accounts are keyed on `email` with a separate `display_name`. **There is no `username` field anywhere.**

```python
async def test_login_returns_token(client):
    await client.post("/api/auth/register",
                      json={"email": "u@x.com", "display_name": "U", "password": "pw-long-enough"})
    r = await client.post("/api/auth/login", json={"email": "u@x.com", "password": "pw-long-enough"})
    assert r.status_code == 200
    assert "access_token" in r.json()
```

### Auth helpers — use the `make_token` fixture

It returns a ready `Authorization` header dict and mints through the real
`create_access_token(user_id, role)`.

```python
async def test_admin_only_endpoint(client, make_token):
    r = await client.get("/api/admin/users", headers=make_token("u1", "admin"))
    assert r.status_code == 200
```

**Never hand-roll a JWT in a test.** Two reasons it will not work:

1. `decode_access_token()` rejects any token whose payload lacks `type: "access"`. A hand-built
   `{"sub", "role", "exp"}` payload is refused even when the signature is valid.
2. `get_current_user` resolves `db.get(User, payload["sub"])` and requires `is_active` — **the user row
   must exist in the test DB.** A token for a fabricated `"u1"` yields 401, not 200. The `make_token`
   fixture creates the row.

This stack signs with **PyJWT** (`import jwt`) and hashes with **`bcrypt` directly**. `python-jose` and
`passlib` are not dependencies — if an inherited example imports `from jose import jwt`, it is wrong here.

### Pure-logic tests — use `SimpleNamespace` duck-typing

For stats rollups, the alias/normalisation tables and the IGC→flight matcher, avoid the DB entirely.
Duck-type the ORM rows and call the function directly.

```python
from types import SimpleNamespace
from flightlog.core.stats import launch_technique_split

def _f(date, technique):
    return SimpleNamespace(flight_date=date, launch_technique=technique)

def test_reverse_share_counts_every_flight():
    flights = [_f(date(2026, 1, 1), "reverse"), _f(date(2026, 1, 2), "forward")]
    assert launch_technique_split(flights)["reverse_pct"] == 50.0
```

### Time-dependent fixtures — do not hardcode a clock time

Build fixture timestamps **relative to `datetime.now(timezone.utc)`**. A hardcoded time makes the suite
pass or fail depending on the hour it runs at. This bites hardest on the IGC→flight matcher, which
compares track durations against logged minutes within a tolerance window.

---

## Coverage expectations

| Area | What's tested |
|---|---|
| Auth | register, login, refresh, `/me`; duplicate email 409; wrong password 401; inactive user 401 |
| Registration gate | `allow_self_registration=False` → 403; admin create still works |
| JWT fail-closed | app refuses to start on empty / short / placeholder `jwt_secret` |
| Error envelope | every error is `{"error": {code, message, details}}`; 422 carries `details.errors`; a validation error does not 500 |
| Health | 200 with service, version, uptime, DB status |
| Static caching | HTML `no-cache` + ETag → 304; `?v=` assets immutable; unversioned `max-age=600`; no CDN refs remain |
| Ownership scoping | another user's row → 404, never 403-with-existence-leak; `owner_id` in a request body is ignored |
| IGC analysis (real) | thermal count / total climb / glide ratio against a known track; **descending spirals excluded**; baro preferred over GNSS; a 0 m baro fix is not discarded |
| IGC matching | unambiguous date auto-attaches; ambiguous multi-flight day reported, never guessed; sha256 re-upload is a no-op |
| Importer | 600 rows in → 600 out; alias hits; idempotent re-run; formula cross-check reports the row-472 change |
| API keys | valid key passes; missing scope → 403; revoked → 401; expired → 401 |

---

## CI

`.github/workflows/test.yml` runs on every push and PR:

```yaml
- run: poetry run pytest --tb=short -q
- run: poetry run ruff check src/ tests/
- run: poetry run ruff format --check src/ tests/
```

**No `continue-on-error`.** Lenticularis carries that flag on its ruff step because an invalid
`requires-python` value makes ruff fail to parse `pyproject.toml` — which is exactly how that bug went
unnoticed for months. A clean repo has no such excuse.

The matrix runs the project's supported Python versions so a runtime upgrade is proven by CI before it
is adopted in the Dockerfile.

---

## Frontend

No Playwright setup yet. The no-build frontend makes it straightforward to add later under
`tests/frontend/`.
