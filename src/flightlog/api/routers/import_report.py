"""
Historical import report.

    GET /api/import-report   — always returns the same frozen v0.2 findings; never re-runs the
                                importer, never writes anything. Not owner-scoped: this describes
                                a system-level historical event, not a per-owner resource.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends

from flightlog.api.dependencies import get_current_user
from flightlog.core.import_history import HISTORICAL_IMPORT_SUMMARY
from flightlog.database.models import User
from flightlog.models.import_report import HistoricalImportReportOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import-report", tags=["import-report"])


@router.get("", response_model=HistoricalImportReportOut)
def get_import_report(
    _current_user: User = Depends(get_current_user),
) -> HistoricalImportReportOut:
    return HistoricalImportReportOut(
        imported_at=HISTORICAL_IMPORT_SUMMARY.imported_at,
        flights_written=HISTORICAL_IMPORT_SUMMARY.flights_written,
        unresolved_gear=[asdict(f) for f in HISTORICAL_IMPORT_SUMMARY.unresolved_gear],
        region_mismatches=[asdict(f) for f in HISTORICAL_IMPORT_SUMMARY.region_mismatches],
        altgain_mismatches=[asdict(f) for f in HISTORICAL_IMPORT_SUMMARY.altgain_mismatches],
        buddy_proposals=[asdict(f) for f in HISTORICAL_IMPORT_SUMMARY.buddy_proposals],
    )
