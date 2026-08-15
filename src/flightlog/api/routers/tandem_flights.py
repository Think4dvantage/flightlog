"""
Tandem flights (the pilot as passenger).

    GET    /api/tandem-flights
    POST   /api/tandem-flights
    GET    /api/tandem-flights/{id}
    PUT    /api/tandem-flights/{id}
    DELETE /api/tandem-flights/{id}

Imported rows (Tandemflüge sheet) and pilot-created rows share this table.
`import_key` is never accepted from the body — only `core/secondary_import.py` sets it.
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
from flightlog.models.secondary import TandemFlightCreate, TandemFlightOut, TandemFlightUpdate

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


@router.post("", response_model=TandemFlightOut, status_code=201)
def create_tandem_flight(
    body: TandemFlightCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemFlight:
    tandem = TandemFlight(owner_id=current_user.id, **body.model_dump())
    db.add(tandem)
    db.commit()
    db.refresh(tandem)
    logger.info("Tandem flight created: %s by %s", tandem.id, current_user.id)
    return tandem


@router.get("/{tandem_id}", response_model=TandemFlightOut)
def get_tandem_flight(
    tandem_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemFlight:
    return _get_own_tandem_flight(tandem_id, current_user, db)


@router.put("/{tandem_id}", response_model=TandemFlightOut)
def update_tandem_flight(
    tandem_id: str,
    body: TandemFlightUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemFlight:
    tandem = _get_own_tandem_flight(tandem_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tandem, field, value)
    db.commit()
    db.refresh(tandem)
    logger.info("Tandem flight updated: %s by %s", tandem.id, current_user.id)
    return tandem


@router.delete("/{tandem_id}", status_code=204)
def delete_tandem_flight(
    tandem_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    tandem = _get_own_tandem_flight(tandem_id, current_user, db)
    db.delete(tandem)
    db.commit()
    logger.info("Tandem flight deleted: %s by %s", tandem_id, current_user.id)
