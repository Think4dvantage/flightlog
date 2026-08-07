"""
Buddies (flying contacts) and the two-sided account-link flow.

    GET    /api/buddies
    POST   /api/buddies
    GET    /api/buddies/{id}
    PUT    /api/buddies/{id}
    DELETE /api/buddies/{id}          — never touches the linked account
    POST   /api/buddies/{id}/link     — always 202, whether or not the email is registered
    POST   /api/buddies/{id}/link/accept   — called by the *linked* pilot, not the buddy's owner
    POST   /api/buddies/{id}/link/decline  — same caller as accept
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.database.db import get_db
from flightlog.database.models import Buddy, User
from flightlog.models.buddies import BuddyCreate, BuddyLinkRequest, BuddyOut, BuddyUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/buddies", tags=["buddies"])


def _get_own_buddy(buddy_id: str, current_user: User, db: Session) -> Buddy:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Buddy, buddy_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Buddy not found")
    return row


def _get_linked_buddy(buddy_id: str, current_user: User, db: Session) -> Buddy:
    """For accept/decline — the caller is the *linked* pilot, not the buddy's owner."""
    row = db.get(Buddy, buddy_id)
    if row is None or row.linked_user_id != current_user.id or row.link_state != "pending":
        raise AppException(404, "ENTITY_NOT_FOUND", "Pending link not found")
    return row


@router.get("", response_model=list[BuddyOut])
def list_buddies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Buddy]:
    return (
        db.execute(
            select(Buddy).where(Buddy.owner_id == current_user.id).order_by(Buddy.display_name)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=BuddyOut, status_code=201)
def create_buddy(
    body: BuddyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Buddy:
    buddy = Buddy(owner_id=current_user.id, **body.model_dump())
    db.add(buddy)
    db.commit()
    db.refresh(buddy)
    logger.info("Buddy created: %s by %s", buddy.id, current_user.id)
    return buddy


@router.get("/{buddy_id}", response_model=BuddyOut)
def get_buddy(
    buddy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Buddy:
    return _get_own_buddy(buddy_id, current_user, db)


@router.put("/{buddy_id}", response_model=BuddyOut)
def update_buddy(
    buddy_id: str,
    body: BuddyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Buddy:
    buddy = _get_own_buddy(buddy_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(buddy, field, value)
    db.commit()
    db.refresh(buddy)
    logger.info("Buddy updated: %s by %s", buddy.id, current_user.id)
    return buddy


@router.delete("/{buddy_id}", status_code=204)
def delete_buddy(
    buddy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    buddy = _get_own_buddy(buddy_id, current_user, db)
    db.delete(buddy)  # never touches the linked account — linked_user_id is enrichment only
    db.commit()
    logger.info("Buddy deleted: %s by %s", buddy_id, current_user.id)


@router.post("/{buddy_id}/link", status_code=202)
def link_buddy(
    buddy_id: str,
    body: BuddyLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    buddy = _get_own_buddy(buddy_id, current_user, db)
    target = db.execute(
        select(User).where(func.lower(User.email) == body.email.lower().strip())
    ).scalar_one_or_none()

    # Always 202 whether or not the email belongs to a registered pilot — a differing
    # response would make this endpoint a user-enumeration oracle. See 04-constraints.md.
    if target is not None:
        buddy.linked_user_id = target.id
        buddy.link_state = "pending"
        db.commit()
    logger.info("Buddy link requested: buddy=%s by=%s", buddy_id, current_user.id)


@router.post("/{buddy_id}/link/accept", response_model=BuddyOut)
def accept_buddy_link(
    buddy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Buddy:
    buddy = _get_linked_buddy(buddy_id, current_user, db)
    buddy.link_state = "confirmed"
    db.commit()
    db.refresh(buddy)
    logger.info("Buddy link accepted: buddy=%s by=%s", buddy_id, current_user.id)
    return buddy


@router.post("/{buddy_id}/link/decline", response_model=BuddyOut)
def decline_buddy_link(
    buddy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Buddy:
    buddy = _get_linked_buddy(buddy_id, current_user, db)
    buddy.link_state = "declined"
    db.commit()
    db.refresh(buddy)
    logger.info("Buddy link declined: buddy=%s by=%s", buddy_id, current_user.id)
    return buddy
