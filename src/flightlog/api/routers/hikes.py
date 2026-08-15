"""
Hikes.

    GET    /api/hikes           — filter: linked (bool)
    POST   /api/hikes
    GET    /api/hikes/{id}
    PUT    /api/hikes/{id}
    DELETE /api/hikes/{id}

Imported rows (Fitnessprogramm sheet) and pilot-created rows share this table.
`import_key` is never accepted from the body — only `core/secondary_import.py` sets it.
A hike's optional `flight_id` link can be set/cleared by hand here (never validated
against ownership, matching the rest of the app's cross-referenced-id convention —
see flights.py's launch_site_id/category_id).
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
from flightlog.models.secondary import HikeCreate, HikeOut, HikeUpdate

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


@router.post("", response_model=HikeOut, status_code=201)
def create_hike(
    body: HikeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    # import_key is never accepted from the body — HikeCreate has no such field at all
    hike = Hike(owner_id=current_user.id, **body.model_dump())
    db.add(hike)
    db.commit()
    db.refresh(hike)
    logger.info("Hike created: %s by %s", hike.id, current_user.id)
    return hike


@router.get("/{hike_id}", response_model=HikeOut)
def get_hike(
    hike_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    return _get_own_hike(hike_id, current_user, db)


@router.put("/{hike_id}", response_model=HikeOut)
def update_hike(
    hike_id: str,
    body: HikeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Hike:
    hike = _get_own_hike(hike_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(hike, field, value)
    db.commit()
    db.refresh(hike)
    logger.info("Hike updated: %s by %s", hike.id, current_user.id)
    return hike


@router.delete("/{hike_id}", status_code=204)
def delete_hike(
    hike_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    hike = _get_own_hike(hike_id, current_user, db)
    db.delete(hike)
    db.commit()
    logger.info("Hike deleted: %s by %s", hike_id, current_user.id)
