"""
Shared test fixtures.

Most of what follows is defensive against traps documented in
.ai/instructions/06-testing-conventions.md. Read the comments before simplifying anything
here — each one cost real debugging time.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import flightlog.config as _fl_config
from flightlog.api.main import create_app
from flightlog.config import (
    APIConfig,
    AuthConfig,
    DatabaseConfig,
    LoggingConfig,
    MainConfig,
    SitesConfig,
    StorageConfig,
)
from flightlog.database.db import _seed_regions, get_db
from flightlog.database.models import Base, User
from flightlog.services.auth import create_access_token, hash_password

JWT_SECRET = "test-secret-that-is-at-least-32-chars!!"

TEST_PASSWORD = "correct-horse-battery"


def build_config(**overrides) -> MainConfig:
    """A complete MainConfig for tests. Overrides are applied to the auth section."""
    auth_kwargs = {
        "jwt_secret": JWT_SECRET,
        # Production defaults to False. Registration tests need it on; the test that
        # asserts the 403 flips it off explicitly.
        "allow_self_registration": True,
    }
    auth_kwargs.update(overrides.pop("auth", {}))

    return MainConfig(
        database=DatabaseConfig(path=":memory:"),
        auth=AuthConfig(**auth_kwargs),
        storage=StorageConfig(**overrides.pop("storage", {})),
        sites=SitesConfig(),
        logging=LoggingConfig(level="warning", file=""),
        api=APIConfig(),
    )


@pytest.fixture(autouse=True)
def patch_config(monkeypatch, tmp_path):
    """
    get_config() checks the module-level _config first, so setting it directly bypasses
    all file I/O at every call site.
    """
    cfg = build_config(storage={"igc_dir": str(tmp_path / "igc")})
    (tmp_path / "igc").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_fl_config, "_config", cfg)
    return cfg


@pytest.fixture
def db_engine():
    """
    poolclass=StaticPool is mandatory, not cosmetic.

    An in-memory SQLite engine defaults to SingletonThreadPool, which opens one connection
    per thread — and every in-memory SQLite connection is its own separate, empty database.
    FastAPI runs sync dependencies (get_db, get_current_user, require_admin — all `def`)
    in a worker threadpool, so they land on a different thread, see none of the tables
    create_all() built here, and fail with `no such table: users`.

    Confusingly, `async def` handlers work fine because their body runs on the event loop
    thread, so the bug only surfaces on endpoints that authenticate.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    _seed_regions(engine)  # real init_db() always seeds regions; tests should see the same state
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest_asyncio.fixture
async def test_app(db_engine, tmp_path):
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    @asynccontextmanager
    async def _test_lifespan(_app):
        yield

    app = create_app()
    app.router.lifespan_context = _test_lifespan

    # Set app.state DIRECTLY. httpx's ASGITransport never emits ASGI lifespan events, so
    # no lifespan_context ever runs under it — state assigned inside one is silently
    # discarded, and routes that read it fail in confusing, seemingly unrelated ways.
    igc_root = tmp_path / "igc"
    igc_root.mkdir(parents=True, exist_ok=True)
    app.state.igc_root = igc_root
    app.state.engine = db_engine

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


@pytest.fixture
def make_user(db_engine):
    """
    Create a real user row. get_current_user resolves db.get(User, sub), so a token for a
    user that does not exist yields 401 — every auth test needs the row, not just a token.
    """
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def _make(
        email: str = "pilot@example.com",
        password: str = TEST_PASSWORD,
        role: str = "pilot",
        is_active: bool = True,
        display_name: str = "Test Pilot",
    ) -> User:
        with factory() as db:
            user = User(
                email=email,
                display_name=display_name,
                hashed_password=hash_password(password),
                role=role,
                is_active=is_active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user

    return _make


@pytest.fixture
def make_token(make_user):
    """
    Returns a ready Authorization header. Mints through the real create_access_token.

    Never hand-roll a JWT in a test: decode_token rejects any payload lacking
    `type: "access"`, and the user row must exist in the test DB.
    """

    def _make(user: User | None = None, **user_kwargs) -> dict[str, str]:
        subject = user or make_user(**user_kwargs)
        token = create_access_token(subject.id, subject.role)
        return {"Authorization": f"Bearer {token}"}

    return _make
