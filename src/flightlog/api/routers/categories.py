"""
Flight categories.

    GET    /api/categories               — filter: include_archived (default false)
    POST   /api/categories
    GET    /api/categories/{id}
    PUT    /api/categories/{id}
    PUT    /api/categories/reorder       — MUST be declared before /{id} routes: FastAPI matches
                                            routes in declaration order, so the reverse order would
                                            swallow /reorder requests into the {id} handler.
    POST   /api/categories/{id}/archive  — sets archived_at; never a hard delete once referenced
    DELETE /api/categories/{id}          — 409 if a flight still references it
"""

from __future__ import annotations

import logging
import re
import unicodedata

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import CODE_CONFLICT, AppException
from flightlog.database.db import get_db
from flightlog.database.models import Flight, FlightCategory, User, utcnow
from flightlog.models.categories import (
    CategoryCreate,
    CategoryOut,
    CategoryReorderRequest,
    CategoryUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _slugify(name: str) -> str:
    """ASCII-folded, hyphenated identifier — good enough for a UniqueConstraint key, not a URL."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "category"


def _get_own_category(category_id: str, current_user: User, db: Session) -> FlightCategory:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(FlightCategory, category_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Category not found")
    return row


@router.get("", response_model=list[CategoryOut])
def list_categories(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FlightCategory]:
    stmt = select(FlightCategory).where(FlightCategory.owner_id == current_user.id)
    if not include_archived:
        stmt = stmt.where(FlightCategory.archived_at.is_(None))
    return db.execute(stmt.order_by(FlightCategory.sort_order)).scalars().all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightCategory:
    max_order = db.execute(
        select(FlightCategory.sort_order)
        .where(FlightCategory.owner_id == current_user.id)
        .order_by(FlightCategory.sort_order.desc())
        .limit(1)
    ).scalar()
    category = FlightCategory(
        owner_id=current_user.id,
        slug=_slugify(body.name),
        sort_order=(max_order + 1) if max_order is not None else 0,
        **body.model_dump(),
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Category created: %s by %s", category.id, current_user.id)
    return category


@router.put("/reorder", response_model=list[CategoryOut])
def reorder_categories(
    body: CategoryReorderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FlightCategory]:
    rows = {
        c.id: c
        for c in db.execute(
            select(FlightCategory).where(FlightCategory.owner_id == current_user.id)
        ).scalars()
    }
    for position, category_id in enumerate(body.ids):
        row = rows.get(category_id)
        if row is None:
            raise AppException(404, "ENTITY_NOT_FOUND", "Category not found")
        row.sort_order = position
    db.commit()
    logger.info("Categories reordered by %s: %s", current_user.id, body.ids)
    return (
        db.execute(
            select(FlightCategory)
            .where(FlightCategory.owner_id == current_user.id)
            .order_by(FlightCategory.sort_order)
        )
        .scalars()
        .all()
    )


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightCategory:
    return _get_own_category(category_id, current_user, db)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    body: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightCategory:
    category = _get_own_category(category_id, current_user, db)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        category.slug = _slugify(changes["name"])
    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    logger.info("Category updated: %s by %s", category.id, current_user.id)
    return category


@router.post("/{category_id}/archive", response_model=CategoryOut)
def archive_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightCategory:
    category = _get_own_category(category_id, current_user, db)
    category.archived_at = utcnow()
    db.commit()
    db.refresh(category)
    logger.info("Category archived: %s by %s", category.id, current_user.id)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    category = _get_own_category(category_id, current_user, db)
    referenced = db.execute(select(Flight.id).where(Flight.category_id == category_id)).first()
    if referenced is not None:
        raise AppException(409, CODE_CONFLICT, "Category is referenced by an existing flight")
    db.delete(category)
    db.commit()
    logger.info("Category deleted: %s by %s", category_id, current_user.id)
