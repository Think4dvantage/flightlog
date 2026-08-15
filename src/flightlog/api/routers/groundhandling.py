"""
Ground-handling sessions.

    GET /api/groundhandling
    GET /api/groundhandling/{id}

Import-and-view only — no POST/PUT/DELETE. A session is only ever created by
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
from flightlog.database.models import GroundhandlingSession, User
from flightlog.models.secondary import GroundhandlingSessionOut

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


@router.get("/{session_id}", response_model=GroundhandlingSessionOut)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundhandlingSession:
    return _get_own_session(session_id, current_user, db)
