"""
Application factory, lifespan and the three global error handlers.

No routes are defined in this module. Domain routers live in `api/routers/<domain>.py`
and every HTML route lives in `api/routers/pages.py`.
"""

from __future__ import annotations

import logging
import sys
import tomllib
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Starlette's HTTPException, not FastAPI's subclass. Unmatched routes and other
# framework-level errors raise the parent class, so a handler registered against the
# subclass never fires for them and those responses escape the typed envelope.
from starlette.exceptions import HTTPException as StarletteHTTPException

from flightlog.api.errors import (
    CODE_INTERNAL_ERROR,
    CODE_VALIDATION_FAILED,
    AppException,
    code_for_status,
    envelope,
)
from flightlog.api.routers import auth as auth_router
from flightlog.api.routers import buddies as buddies_router
from flightlog.api.routers import categories as categories_router
from flightlog.api.routers import flights as flights_router
from flightlog.api.routers import gliders as gliders_router
from flightlog.api.routers import goals as goals_router
from flightlog.api.routers import groundhandling as groundhandling_router
from flightlog.api.routers import harnesses as harnesses_router
from flightlog.api.routers import health as health_router
from flightlog.api.routers import hikes as hikes_router
from flightlog.api.routers import igc as igc_router
from flightlog.api.routers import import_report as import_report_router
from flightlog.api.routers import pages as pages_router
from flightlog.api.routers import regions as regions_router
from flightlog.api.routers import sites as sites_router
from flightlog.api.routers import stats as stats_router
from flightlog.api.routers import tandem_flights as tandem_flights_router
from flightlog.config import load_config, log_effective_config
from flightlog.database.db import init_db, seed_bootstrap_admin

logger = logging.getLogger(__name__)


def _resolve_version() -> str:
    """
    The app version is the static-asset cache key, so resolving it wrongly is not
    cosmetic — a stuck version means returning users keep stale CSS and JS forever.

    importlib.metadata only works when the package is pip-installed. The container runs
    `poetry install --no-root` and puts src/ on PYTHONPATH, so there is no distribution
    metadata there; fall back to reading the pyproject.toml that sits beside it.
    """
    try:
        return pkg_version("flightlog")
    except PackageNotFoundError:
        pass

    # /app/pyproject.toml in the container, repo root in a source checkout.
    for candidate in (
        Path(__file__).resolve().parents[2].parent / "pyproject.toml",
        Path.cwd() / "pyproject.toml",
    ):
        try:
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if version:
                return version
        except (OSError, tomllib.TOMLDecodeError):
            continue

    logger.warning("Could not resolve app version — static asset cache-busting is degraded")
    return "0.0.0-dev"


APP_VERSION = _resolve_version()

STATIC_DIR = Path(__file__).resolve().parents[2].parent / "static"

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def _configure_logging(level: str, log_file: str) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    _configure_logging(cfg.logging.level, cfg.logging.file)

    logger.info("Starting flightlog %s", APP_VERSION)
    log_effective_config(cfg)

    # Fail closed before anything else can accept a request. A dev placeholder secret
    # reaching production is a total auth bypass, so this raises rather than warns.
    cfg.auth.validate_secret()
    logger.info("JWT secret validated")

    engine = init_db(cfg.database.path)
    app.state.engine = engine
    seed_bootstrap_admin(
        engine,
        cfg.auth.bootstrap_admin_email,
        cfg.auth.bootstrap_admin_password,
    )

    igc_root = Path(cfg.storage.igc_dir)
    igc_root.mkdir(parents=True, exist_ok=True)
    app.state.igc_root = igc_root
    logger.info("IGC storage ready at %s", igc_root.resolve())

    logger.info("HTTP server ready on %s:%d", cfg.api.host, cfg.api.port)
    yield
    logger.info("Shutting down flightlog %s", APP_VERSION)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Flightlog",
        description="Multiuser paragliding flight log with IGC analysis.",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = CSP

        # Cache-busted assets are immutable; unversioned ones get a short TTL so a
        # missed version bump degrades to "stale for 10 minutes", not "stale for a year".
        if request.url.path.startswith("/static/"):
            if "v=" in (request.url.query or ""):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=600"

        return response

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ---- error handlers: every error leaves as the typed envelope ----

    @app.exception_handler(AppException)
    async def _app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("AppException %s: %s", exc.code, exc.message, exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = code_for_status(exc.status_code)
        if exc.status_code >= 500:
            logger.error("HTTPException %d: %s", exc.status_code, exc.detail, exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # jsonable_encoder is required, not cosmetic: Pydantic v2 puts the exception
        # object itself into ctx.error, which JSONResponse cannot serialise — without
        # this the handler 500s while trying to report a 422.
        return JSONResponse(
            status_code=422,
            content=envelope(
                CODE_VALIDATION_FAILED,
                "Request validation failed",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=envelope(CODE_INTERNAL_ERROR, "An internal error occurred"),
        )

    # ---- routers ----

    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(regions_router.router)
    app.include_router(sites_router.router)
    app.include_router(gliders_router.router)
    app.include_router(harnesses_router.router)
    app.include_router(categories_router.router)
    app.include_router(buddies_router.router)
    app.include_router(flights_router.router)
    app.include_router(import_report_router.router)
    app.include_router(igc_router.router)
    app.include_router(hikes_router.router)
    app.include_router(groundhandling_router.router)
    app.include_router(tandem_flights_router.router)
    app.include_router(goals_router.router)
    app.include_router(stats_router.router)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(pages_router.router)

    return app


app = create_app()
