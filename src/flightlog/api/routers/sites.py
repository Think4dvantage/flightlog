"""
Sites.

    GET    /api/sites             — filters: is_launch, is_landing, region_id
    POST   /api/sites
    GET    /api/sites/{id}
    PUT    /api/sites/{id}
    DELETE /api/sites/{id}        — 409 if a flight still references it
    PUT    /api/sites/{id}/prefs  — upserts the caller's own user_site_prefs row
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import CODE_CONFLICT, AppException
from flightlog.database.db import get_db
from flightlog.database.models import Flight, Site, User, UserSitePref
from flightlog.models.sites import (
    SiteCreate,
    SiteOut,
    SiteUpdate,
    UserSitePrefOut,
    UserSitePrefUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _get_own_site(site_id: str, current_user: User, db: Session) -> Site:
    """404 whether the row is missing or simply not yours — never a 403. See
    02-backend-conventions.md."""
    row = db.get(Site, site_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Site not found")
    return row


@router.get("", response_model=list[SiteOut])
def list_sites(
    is_launch: bool | None = None,
    is_landing: bool | None = None,
    region_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Site]:
    stmt = select(Site).where(Site.owner_id == current_user.id)
    if is_launch is not None:
        stmt = stmt.where(Site.is_launch == is_launch)
    if is_landing is not None:
        stmt = stmt.where(Site.is_landing == is_landing)
    if region_id is not None:
        stmt = stmt.where(Site.region_id == region_id)
    return db.execute(stmt.order_by(Site.name)).scalars().all()


@router.post("", response_model=SiteOut, status_code=201)
def create_site(
    body: SiteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Site:
    site = Site(owner_id=current_user.id, **body.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    logger.info("Site created: %s by %s", site.id, current_user.id)
    return site


@router.get("/{site_id}", response_model=SiteOut)
def get_site(
    site_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Site:
    return _get_own_site(site_id, current_user, db)


@router.put("/{site_id}", response_model=SiteOut)
def update_site(
    site_id: str,
    body: SiteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Site:
    site = _get_own_site(site_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    logger.info("Site updated: %s by %s", site.id, current_user.id)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    site = _get_own_site(site_id, current_user, db)
    referenced = db.execute(
        select(Flight.id).where(
            (Flight.launch_site_id == site_id) | (Flight.landing_site_id == site_id)
        )
    ).first()
    if referenced is not None:
        raise AppException(409, CODE_CONFLICT, "Site is referenced by an existing flight")
    db.delete(site)
    db.commit()
    logger.info("Site deleted: %s by %s", site_id, current_user.id)


@router.put("/{site_id}/prefs", response_model=UserSitePrefOut)
def upsert_site_prefs(
    site_id: str,
    body: UserSitePrefUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSitePref:
    _get_own_site(site_id, current_user, db)  # ensures the site exists and is visible

    pref = db.get(UserSitePref, (current_user.id, site_id))
    if pref is None:
        pref = UserSitePref(user_id=current_user.id, site_id=site_id)
        db.add(pref)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)
    db.commit()
    db.refresh(pref)
    logger.info("Site prefs updated: user=%s site=%s", current_user.id, site_id)
    return pref
