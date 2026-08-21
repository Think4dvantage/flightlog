"""
Statistics.

    GET /api/stats/totals
    GET /api/stats/time-breakdown
    GET /api/stats/distribution
    GET /api/stats/monthly-extremes
    GET /api/stats/airtime-by-month
    GET /api/stats/xc-progression
    GET /api/stats/personal-bests
    GET /api/stats/matrix/{dimension}   -- site|region|glider|harness|category|buddy
    GET /api/stats/launch-technique
    GET /api/stats/igc-rollup
    GET /api/stats/progression

Every route is owner-scoped directly in its query — no path-parameter id anywhere in this
router to leak another owner's existence through (contracts/endpoints.md). Zero-data cases
return the shape's natural empty form with 200, never a 404 or 500.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.core import stats as stats_core
from flightlog.database.db import get_db
from flightlog.database.models import User
from flightlog.models.stats import (
    AirtimeByMonthOut,
    DimensionYearMatrixOut,
    DistributionOut,
    IgcRollupOut,
    LaunchTechniqueOut,
    MonthlyExtremesOut,
    PersonalBestOut,
    ProgressionOut,
    TimeBreakdownOut,
    TotalsOut,
    XcProgressionOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/totals", response_model=TotalsOut)
def get_totals(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TotalsOut:
    return stats_core.totals(db, current_user.id)


@router.get("/time-breakdown", response_model=TimeBreakdownOut)
def get_time_breakdown(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TimeBreakdownOut:
    return stats_core.time_breakdown(db, current_user.id)


@router.get("/distribution", response_model=DistributionOut)
def get_distribution(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DistributionOut:
    return stats_core.distribution(db, current_user.id)


@router.get("/monthly-extremes", response_model=MonthlyExtremesOut)
def get_monthly_extremes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MonthlyExtremesOut:
    return stats_core.monthly_extremes(db, current_user.id)


@router.get("/airtime-by-month", response_model=AirtimeByMonthOut)
def get_airtime_by_month(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AirtimeByMonthOut:
    return stats_core.airtime_by_month(db, current_user.id)


@router.get("/xc-progression", response_model=XcProgressionOut)
def get_xc_progression(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> XcProgressionOut:
    return stats_core.xc_progression(db, current_user.id)


@router.get("/personal-bests", response_model=list[PersonalBestOut])
def get_personal_bests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PersonalBestOut]:
    return stats_core.personal_bests(db, current_user.id)


@router.get("/matrix/{dimension}", response_model=DimensionYearMatrixOut)
def get_matrix(
    dimension: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DimensionYearMatrixOut:
    # A plain str + allowlist lookup, not Literal[...] — an invalid dimension is a routing
    # concern (which sub-resource) and must 404, not 422 (contracts/endpoints.md). Literal
    # would make FastAPI reject it with a 422 before this handler ever runs.
    if dimension not in stats_core.DIMENSIONS:
        raise AppException(404, "ENTITY_NOT_FOUND", f"Unknown stats dimension: {dimension}")
    return stats_core.year_matrix(db, current_user.id, dimension)


@router.get("/launch-technique", response_model=LaunchTechniqueOut)
def get_launch_technique(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> LaunchTechniqueOut:
    return stats_core.launch_technique(db, current_user.id)


@router.get("/igc-rollup", response_model=IgcRollupOut)
def get_igc_rollup(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> IgcRollupOut:
    return stats_core.igc_rollup(db, current_user.id)


@router.get("/progression", response_model=ProgressionOut)
def get_progression(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProgressionOut:
    return stats_core.progression(db, current_user.id)
