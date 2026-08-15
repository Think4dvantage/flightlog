"""
Hikes.

    GET /api/hikes           — filter: linked (bool)
    GET /api/hikes/{id}

Import-and-view only (specs/004-secondary-sheets-xcontest spec.md's Out of Scope) — no
POST/PUT/DELETE. A hike is only ever created by core/secondary_import.py.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.database.db import get_db
from flightlog.database.models import Hike, User
from flightlog.models.secondary import HikeOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hikes", tags=["hikes"])


def _get_own_hike(hike_id: str, current_user: User, db: Session) -> Hike:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Hike, hike_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Hike not found")
    return row


@router.get("", response_model=list[HikeOut])
def list_hikes(
    linked: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Hike]:
    stmt = select(Hike).where(Hike.owner_id == current_user.id)
    if linked is True:
        stmt = stmt.where(Hike.flight_id.isnot(None))
    elif linked is False:
        stmt = stmt.where(Hike.flight_id.is_(None))
    return db.execute(stmt.order_by(Hike.hike_date.desc())).scalars().all()


@router.get("/{hike_id}", response_model=HikeOut)
def get_hike(
    hike_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    return _get_own_hike(hike_id, current_user, db)
