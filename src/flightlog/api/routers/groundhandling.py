"""
Ground-handling sessions.

    GET    /api/groundhandling
    POST   /api/groundhandling
    GET    /api/groundhandling/{id}
    PUT    /api/groundhandling/{id}
    DELETE /api/groundhandling/{id}

Imported rows (Groundhandling sheet) and pilot-created rows share this table.
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
from flightlog.database.models import GroundhandlingSession, User
from flightlog.models.secondary import (
    GroundhandlingSessionCreate,
    GroundhandlingSessionOut,
    GroundhandlingSessionUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/groundhandling", tags=["groundhandling"])


def _get_own_session(session_id: str, current_user: User, db: Session) -> GroundhandlingSession:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(GroundhandlingSession, session_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Groundhandling session not found")
    return row


@router.get("", response_model=list[GroundhandlingSessionOut])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroundhandlingSession]:
    stmt = select(GroundhandlingSession).where(GroundhandlingSession.owner_id == current_user.id)
    return db.execute(stmt.order_by(GroundhandlingSession.session_date.desc())).scalars().all()


@router.post("", response_model=GroundhandlingSessionOut, status_code=201)
def create_session(
    body: GroundhandlingSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundhandlingSession:
    session = GroundhandlingSession(owner_id=current_user.id, **body.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Groundhandling session created: %s by %s", session.id, current_user.id)
    return session


@router.get("/{session_id}", response_model=GroundhandlingSessionOut)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundhandlingSession:
    return _get_own_session(session_id, current_user, db)


@router.put("/{session_id}", response_model=GroundhandlingSessionOut)
def update_session(
    session_id: str,
    body: GroundhandlingSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundhandlingSession:
    session = _get_own_session(session_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    logger.info("Groundhandling session updated: %s by %s", session.id, current_user.id)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = _get_own_session(session_id, current_user, db)
    db.delete(session)
    db.commit()
    logger.info("Groundhandling session deleted: %s by %s", session_id, current_user.id)
