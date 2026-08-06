"""Security headers, static-asset caching and the server-side cache-busting rewrite."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"

PAGES = ["/", "/login", "/register"]


@pytest.mark.parametrize("path", PAGES)
async def test_pages_render(client, path):
    r = await client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("path", PAGES)
async def test_pages_are_revalidated_not_cached(client, path):
    r = await client.get(path)
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["etag"]


@pytest.mark.parametrize("path", PAGES)
async def test_etag_produces_a_304(client, path):
    first = await client.get(path)
    etag = first.headers["etag"]

    second = await client.get(path, headers={"If-None-Match": etag})
    assert second.status_code == 304


@pytest.mark.parametrize("path", PAGES)
async def test_asset_references_are_cache_busted(client, path, test_app):
    """
    Every /static reference in served HTML must carry ?v=<version>. Without it a deploy
    leaves returning users on stale CSS and JS.
    """
    html = (await client.get(path)).text
    refs = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)

    assert refs, f"{path} references no static assets — the test would pass vacuously"
    for ref in refs:
        assert f"?v={test_app.version}" in ref, f"{ref} is not cache-busted"


def test_app_version_matches_pyproject():
    """
    The version IS the static-asset cache key. importlib.metadata returns nothing when
    the package is not pip-installed — which is exactly the container's situation, since
    the image runs `poetry install --no-root`. A stuck "0.0.0-dev" would silently pin
    every returning browser to stale assets across every future deploy.
    """
    import tomllib

    from flightlog.api.main import APP_VERSION

    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == APP_VERSION
    assert APP_VERSION != "0.0.0-dev"


async def test_versioned_assets_are_immutable(client):
    r = await client.get("/static/shared.css?v=9.9.9")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_unversioned_assets_get_a_short_ttl(client):
    """A missed version bump should degrade to 10 minutes stale, not a year."""
    r = await client.get("/static/shared.css")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=600"


async def test_security_headers_are_present(client):
    r = await client.get("/login")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


async def test_csp_blocks_third_party_scripts(client):
    """script-src 'self' is what makes vendoring mandatory rather than a preference."""
    csp = (await client.get("/login")).headers["content-security-policy"]
    script_src = next(part for part in csp.split(";") if part.strip().startswith("script-src"))
    assert "'self'" in script_src
    assert "http" not in script_src


def test_no_page_references_a_cdn():
    """A CDN reference is browser-blocked by CSP, so it fails silently at runtime."""
    offenders = []
    for html in STATIC_DIR.glob("*.html"):
        text = html.read_text(encoding="utf-8")
        for match in re.findall(r'(?:src|href)="(https?://[^"]+)"', text):
            offenders.append(f"{html.name}: {match}")

    assert not offenders, "external asset references found: " + ", ".join(offenders)


def test_vendored_libraries_are_present():
    assert (STATIC_DIR / "vendor" / "leaflet" / "leaflet.js").is_file()
    assert (STATIC_DIR / "vendor" / "leaflet" / "leaflet.css").is_file()
    assert (STATIC_DIR / "vendor" / "chartjs" / "chart.umd.js").is_file()


def test_each_page_has_exactly_one_module_script():
    for html in STATIC_DIR.glob("*.html"):
        text = html.read_text(encoding="utf-8")
        count = len(re.findall(r'<script\s+type="module"', text))
        assert count == 1, f"{html.name} has {count} module scripts, expected exactly 1"
