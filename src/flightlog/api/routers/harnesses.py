"""
Harnesses.

    GET    /api/harnesses               — filter: include_retired (default false)
    POST   /api/harnesses
    GET    /api/harnesses/{id}
    PUT    /api/harnesses/{id}
    POST   /api/harnesses/{id}/retire   — sets retired_at; never a hard delete once referenced
    DELETE /api/harnesses/{id}          — 409 if a flight still references it
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import CODE_CONFLICT, AppException
from flightlog.database.db import get_db
from flightlog.database.models import Flight, Harness, User, utcnow
from flightlog.models.harnesses import HarnessCreate, HarnessOut, HarnessUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/harnesses", tags=["harnesses"])


def _get_own_harness(harness_id: str, current_user: User, db: Session) -> Harness:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Harness, harness_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Harness not found")
    return row


@router.get("", response_model=list[HarnessOut])
def list_harnesses(
    include_retired: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Harness]:
    stmt = select(Harness).where(Harness.owner_id == current_user.id)
    if not include_retired:
        stmt = stmt.where(Harness.retired_at.is_(None))
    return db.execute(stmt.order_by(Harness.brand, Harness.model)).scalars().all()


@router.post("", response_model=HarnessOut, status_code=201)
def create_harness(
    body: HarnessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Harness:
    harness = Harness(owner_id=current_user.id, **body.model_dump())
    db.add(harness)
    db.commit()
    db.refresh(harness)
    logger.info("Harness created: %s by %s", harness.id, current_user.id)
    return harness


@router.get("/{harness_id}", response_model=HarnessOut)
def get_harness(
    harness_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Harness:
    return _get_own_harness(harness_id, current_user, db)


@router.put("/{harness_id}", response_model=HarnessOut)
def update_harness(
    harness_id: str,
    body: HarnessUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Harness:
    harness = _get_own_harness(harness_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(harness, field, value)
    db.commit()
    db.refresh(harness)
    logger.info("Harness updated: %s by %s", harness.id, current_user.id)
    return harness


@router.post("/{harness_id}/retire", response_model=HarnessOut)
def retire_harness(
    harness_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Harness:
    harness = _get_own_harness(harness_id, current_user, db)
    harness.retired_at = utcnow()
    db.commit()
    db.refresh(harness)
    logger.info("Harness retired: %s by %s", harness.id, current_user.id)
    return harness


@router.delete("/{harness_id}", status_code=204)
def delete_harness(
    harness_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    harness = _get_own_harness(harness_id, current_user, db)
    referenced = db.execute(select(Flight.id).where(Flight.harness_id == harness_id)).first()
    if referenced is not None:
        raise AppException(409, CODE_CONFLICT, "Harness is referenced by an existing flight")
    db.delete(harness)
    db.commit()
    logger.info("Harness deleted: %s by %s", harness_id, current_user.id)
