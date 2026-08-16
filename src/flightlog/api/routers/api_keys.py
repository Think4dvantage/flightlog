"""
Pilot-facing API key management (JWT-authenticated, the pilot's own browser session).

    GET    /api/keys               — key_prefix only, never key_hash or the plaintext
    POST   /api/keys               — response includes the full plaintext key exactly once
    POST   /api/keys/{id}/revoke   — immediate kill switch, effective on the key's next use
    DELETE /api/keys/{id}          — hard-deletes the management row; only once already
                                      revoked (does not un-revoke or resurrect access)

Never confuse this with `api/routers/integration.py`, which is API-key-authenticated and
serves the *external* tool, not the pilot.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import CODE_CONFLICT, CODE_ENTITY_NOT_FOUND, AppException
from flightlog.database.db import get_db
from flightlog.database.models import ApiKey, User
from flightlog.database.models import utcnow as db_utcnow
from flightlog.models.apikeys import ApiKeyCreateIn, ApiKeyCreateOut, ApiKeyOut
from flightlog.services.apikeys import mint_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


def _get_own_key(key_id: str, current_user: User, db: Session) -> ApiKey:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(ApiKey, key_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, CODE_ENTITY_NOT_FOUND, "API key not found")
    return row


def _to_out(row: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=row.scopes.split(),
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyOut]:
    rows = (
        db.execute(
            select(ApiKey)
            .where(ApiKey.owner_id == current_user.id)
            .order_by(ApiKey.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_to_out(row) for row in rows]


@router.post("", response_model=ApiKeyCreateOut, status_code=201)
def create_key(
    body: ApiKeyCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreateOut:
    minted = mint_key()
    row = ApiKey(
        owner_id=current_user.id,
        name=body.name,
        key_prefix=minted.key_prefix,
        key_hash=minted.key_hash,
        scopes=" ".join(body.scopes),
        expires_at=body.expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("API key created: %s by %s", row.id, current_user.id)
    out = _to_out(row)
    return ApiKeyCreateOut(**out.model_dump(), key=minted.plaintext)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyOut:
    row = _get_own_key(key_id, current_user, db)
    if row.revoked_at is None:
        row.revoked_at = db_utcnow()
        db.commit()
        db.refresh(row)
        logger.info("API key revoked: %s by %s", row.id, current_user.id)
    return _to_out(row)


@router.delete("/{key_id}", status_code=204)
def delete_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = _get_own_key(key_id, current_user, db)
    if row.revoked_at is None:
        raise AppException(
            409, CODE_CONFLICT, "Revoke the key before deleting it", {"key_id": key_id}
        )
    db.delete(row)
    db.commit()
    logger.info("API key deleted: %s by %s", key_id, current_user.id)
