"""
Regions.

    GET /api/regions   — shared reference data, same result for every pilot; still requires auth
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.database.db import get_db
from flightlog.database.models import Region, User
from flightlog.models.regions import RegionOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("", response_model=list[RegionOut])
def list_regions(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Region]:
    return db.execute(select(Region).order_by(Region.sort_order)).scalars().all()
