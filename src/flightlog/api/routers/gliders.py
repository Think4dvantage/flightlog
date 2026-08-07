"""
Gliders.

    GET    /api/gliders               — filter: include_retired (default false)
    POST   /api/gliders
    GET    /api/gliders/{id}
    PUT    /api/gliders/{id}
    POST   /api/gliders/{id}/retire   — sets retired_at; never a hard delete once referenced
    DELETE /api/gliders/{id}          — 409 if a flight still references it
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import CODE_CONFLICT, AppException
from flightlog.database.db import get_db
from flightlog.database.models import Flight, Glider, User, utcnow
from flightlog.models.gliders import GliderCreate, GliderOut, GliderUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gliders", tags=["gliders"])


def _get_own_glider(glider_id: str, current_user: User, db: Session) -> Glider:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Glider, glider_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Glider not found")
    return row


@router.get("", response_model=list[GliderOut])
def list_gliders(
    include_retired: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Glider]:
    stmt = select(Glider).where(Glider.owner_id == current_user.id)
    if not include_retired:
        stmt = stmt.where(Glider.retired_at.is_(None))
    return db.execute(stmt.order_by(Glider.brand, Glider.model)).scalars().all()


@router.post("", response_model=GliderOut, status_code=201)
def create_glider(
    body: GliderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Glider:
    glider = Glider(owner_id=current_user.id, **body.model_dump())
    db.add(glider)
    db.commit()
    db.refresh(glider)
    logger.info("Glider created: %s by %s", glider.id, current_user.id)
    return glider


@router.get("/{glider_id}", response_model=GliderOut)
def get_glider(
    glider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Glider:
    return _get_own_glider(glider_id, current_user, db)


@router.put("/{glider_id}", response_model=GliderOut)
def update_glider(
    glider_id: str,
    body: GliderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Glider:
    glider = _get_own_glider(glider_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(glider, field, value)
    db.commit()
    db.refresh(glider)
    logger.info("Glider updated: %s by %s", glider.id, current_user.id)
    return glider


@router.post("/{glider_id}/retire", response_model=GliderOut)
def retire_glider(
    glider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Glider:
    glider = _get_own_glider(glider_id, current_user, db)
    glider.retired_at = utcnow()
    db.commit()
    db.refresh(glider)
    logger.info("Glider retired: %s by %s", glider.id, current_user.id)
    return glider


@router.delete("/{glider_id}", status_code=204)
def delete_glider(
    glider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    glider = _get_own_glider(glider_id, current_user, db)
    referenced = db.execute(select(Flight.id).where(Flight.glider_id == glider_id)).first()
    if referenced is not None:
        raise AppException(409, CODE_CONFLICT, "Glider is referenced by an existing flight")
    db.delete(glider)
    db.commit()
    logger.info("Glider deleted: %s by %s", glider_id, current_user.id)
