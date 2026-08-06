"""
Health endpoint.

**This router is unauthenticated by design** — it is the only one in v0.1 without an auth
dependency, and that is exactly why it lives in its own file.

Liveness vs readiness: a degraded non-critical subsystem reports "degraded" at HTTP 200 so
the UI stays reachable and can show the operator what is wrong. 503 is reserved for
"cannot serve at all" — the database being unreachable.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from flightlog.config import get_config
from flightlog.database.db import check_db_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_STARTED_AT = time.monotonic()


def _igc_storage_health() -> str:
    path = Path(get_config().storage.igc_dir)
    if not path.is_dir():
        return "missing"
    probe = path / ".healthcheck"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        logger.warning("IGC storage is not writable at %s: %s", path, exc)
        return "not writable"
    return "ok"


@router.get("/health")
def health(request: Request) -> JSONResponse:
    db_status = check_db_health(getattr(request.app.state, "engine", None))
    igc_status = _igc_storage_health()

    checks: dict[str, str] = {"sqlite": db_status, "igc_storage": igc_status}

    if db_status != "ok":
        status, http_code = "error", 503
    elif igc_status != "ok":
        status, http_code = "degraded", 200
    else:
        status, http_code = "ok", 200

    body: dict[str, Any] = {
        "status": status,
        "service": "flightlog",
        "version": request.app.version,
        "uptime_seconds": round(time.monotonic() - _STARTED_AT),
        "checks": checks,
    }

    if status != "ok":
        logger.warning("Health check reported %s: %s", status, checks)

    return JSONResponse(status_code=http_code, content=body)
