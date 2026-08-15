"""
Tandem flights (the pilot as passenger).

    GET /api/tandem-flights
    GET /api/tandem-flights/{id}

Import-and-view only — no POST/PUT/DELETE. A tandem flight is only ever created by
core/secondary_import.py.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.database.db import get_db
from flightlog.database.models import TandemFlight, User
from flightlog.models.secondary import TandemFlightOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tandem-flights", tags=["tandem-flights"])


def _get_own_tandem_flight(tandem_id: str, current_user: User, db: Session) -> TandemFlight:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(TandemFlight, tandem_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Tandem flight not found")
    return row


@router.get("", response_model=list[TandemFlightOut])
def list_tandem_flights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TandemFlight]:
    stmt = select(TandemFlight).where(TandemFlight.owner_id == current_user.id)
    return db.execute(stmt.order_by(TandemFlight.flight_date.desc())).scalars().all()


@router.get("/{tandem_id}", response_model=TandemFlightOut)
def get_tandem_flight(
    tandem_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemFlight:
    return _get_own_tandem_flight(tandem_id, current_user, db)
