"""
Goals.

    GET    /api/goals                — filter: status
    POST   /api/goals
    GET    /api/goals/{id}
    PUT    /api/goals/{id}
    DELETE /api/goals/{id}
    POST   /api/goals/{id}/mark-done — sets status="done"; a dedicated action, not a bare PUT
                                        field edit, mirroring gliders.py's POST /{id}/retire
                                        pattern for a status transition that's really an event

The one imported type in this feature that stays fully editable afterward — every other
secondary-sheet import (hikes, groundhandling, tandem flights) is GET-only.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.database.db import get_db
from flightlog.database.models import Goal, User
from flightlog.models.secondary import GoalCreate, GoalOut, GoalUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _get_own_goal(goal_id: str, current_user: User, db: Session) -> Goal:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Goal, goal_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Goal not found")
    return row


@router.get("", response_model=list[GoalOut])
def list_goals(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Goal]:
    stmt = select(Goal).where(Goal.owner_id == current_user.id)
    if status is not None:
        stmt = stmt.where(Goal.status == status)
    return db.execute(stmt.order_by(Goal.created_at.desc())).scalars().all()


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(
    body: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    # import_key is never accepted from the body — GoalCreate has no such field at all
    goal = Goal(owner_id=current_user.id, **body.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    logger.info("Goal created: %s by %s", goal.id, current_user.id)
    return goal


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    return _get_own_goal(goal_id, current_user, db)


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    goal = _get_own_goal(goal_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    logger.info("Goal updated: %s by %s", goal.id, current_user.id)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    goal = _get_own_goal(goal_id, current_user, db)
    db.delete(goal)
    db.commit()
    logger.info("Goal deleted: %s by %s", goal_id, current_user.id)


@router.post("/{goal_id}/mark-done", response_model=GoalOut)
def mark_goal_done(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    goal = _get_own_goal(goal_id, current_user, db)
    goal.status = "done"
    db.commit()
    db.refresh(goal)
    logger.info("Goal marked done: %s by %s", goal.id, current_user.id)
    return goal
