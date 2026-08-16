"""
HTML page routes.

**Every HTML route in the application lives here** — never in main.py, never in a domain
router. All are `include_in_schema=False` so they stay out of the OpenAPI document.

Cache-busting is server-side: asset references in the HTML are rewritten to carry
`?v=<app-version>`, and `main.py` serves anything with a `v=` query as immutable. The
version in pyproject.toml therefore *is* the cache key — ship a static change without
bumping it and returning users keep the old file for up to a year.
"""

from __future__ import annotations

import hashlib
import logging
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)

STATIC_DIR = Path(__file__).resolve().parents[3].parent / "static"

# Matches src="/static/..." and href="/static/..." without an existing query string.
_ASSET_REF = re.compile(r'((?:src|href)=")(/static/[^"?]+)(")')


def _rewrite_assets(html: str, version: str) -> str:
    return _ASSET_REF.sub(rf"\1\2?v={version}\3", html)


@lru_cache(maxsize=64)
def _render(name: str, version: str) -> tuple[str, str]:
    """Return (html, etag). Cached per (page, version) — a version bump invalidates it."""
    path = STATIC_DIR / name
    html = _rewrite_assets(path.read_text(encoding="utf-8"), version)
    etag = '"' + hashlib.sha256(html.encode("utf-8")).hexdigest()[:32] + '"'
    return html, etag


def _page(request: Request, name: str) -> Response:
    version = request.app.version
    try:
        html, etag = _render(name, version)
    except FileNotFoundError:
        logger.error("Page template missing: %s", STATIC_DIR / name)
        return HTMLResponse("<h1>404 — page not found</h1>", status_code=404)

    # HTML is always revalidated; the ETag turns that into a cheap 304.
    headers = {"Cache-Control": "no-cache", "ETag": etag}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return HTMLResponse(html, headers=headers)


@router.get("/")
def index(request: Request) -> Response:
    return _page(request, "index.html")


@router.get("/login")
def login_page(request: Request) -> Response:
    return _page(request, "login.html")


@router.get("/register")
def register_page(request: Request) -> Response:
    return _page(request, "register.html")


@router.get("/flights")
def flights_page(request: Request) -> Response:
    return _page(request, "flights.html")


@router.get("/flights/{flight_id}")
def flight_detail_page(request: Request, flight_id: str) -> Response:
    return _page(request, "flight-detail.html")


@router.get("/sites")
def sites_page(request: Request) -> Response:
    return _page(request, "sites.html")


@router.get("/equipment")
def equipment_page(request: Request) -> Response:
    return _page(request, "equipment.html")


@router.get("/igc")
def igc_bulk_page(request: Request) -> Response:
    return _page(request, "igc.html")


@router.get("/hikes")
def hikes_page(request: Request) -> Response:
    return _page(request, "hikes.html")


@router.get("/groundhandling")
def groundhandling_page(request: Request) -> Response:
    return _page(request, "groundhandling.html")


@router.get("/tandem-flights")
def tandem_flights_page(request: Request) -> Response:
    return _page(request, "tandem-flights.html")


@router.get("/goals")
def goals_page(request: Request) -> Response:
    return _page(request, "goals.html")


@router.get("/contacts")
def contacts_page(request: Request) -> Response:
    return _page(request, "contacts.html")


@router.get("/stats")
def stats_page(request: Request) -> Response:
    return _page(request, "stats.html")


@router.get("/api-keys")
def api_keys_page(request: Request) -> Response:
    return _page(request, "api-keys.html")
