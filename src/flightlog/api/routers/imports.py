"""
Self-service spreadsheet import (v0.9.8, specs/008-self-service-import).

    POST   /api/imports/columns   — upload a file, get back its column headers + samples
    POST   /api/imports/preview   — upload + mapping, dry-run (no writes)
    POST   /api/imports/commit    — upload + mapping, writes for real
    GET    /api/imports           — this pilot's past import runs
    DELETE /api/imports/{id}      — undo a run

JWT-authenticated, owner-scoped like every other domain router — never confuse with
`api/routers/integration.py`'s API-key-authenticated external surface. The file is re-sent on
every step (columns/preview/commit) rather than cached server-side between wizard steps —
deliberately stateless, see `specs/008-self-service-import/plan.md`.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.config import get_config
from flightlog.core import spreadsheet_import as importer
from flightlog.database.db import get_db
from flightlog.database.models import ImportRun, User
from flightlog.models.imports import (
    ImportColumnsOut,
    ImportCommitOut,
    ImportMappingIn,
    ImportPreviewOut,
    ImportRunOut,
    ImportUndoOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/imports", tags=["imports"])

_ALLOWED_EXTENSIONS = (".xlsx", ".csv")


def _get_own_import_run(run_id: str, current_user: User, db: Session) -> ImportRun:
    row = db.get(ImportRun, run_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Import run not found")
    return row


def _read_upload(file: UploadFile) -> bytes:
    filename = file.filename or ""
    if not filename.lower().endswith(_ALLOWED_EXTENSIONS):
        raise AppException(
            422,
            "VALIDATION_FAILED",
            "Only .xlsx or .csv files are supported",
            {"filename": filename},
        )
    data = file.file.read()
    max_bytes = get_config().storage.max_import_bytes
    if len(data) > max_bytes:
        raise AppException(
            422,
            "VALIDATION_FAILED",
            f"{filename}: file too large",
            {"max_bytes": max_bytes, "actual_bytes": len(data)},
        )
    return data


def _parse_mapping(mapping: str) -> dict[str, str]:
    try:
        raw = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise AppException(422, "VALIDATION_FAILED", "mapping is not valid JSON") from exc
    try:
        return ImportMappingIn(mapping=raw).mapping
    except ValidationError as exc:
        # jsonable_encoder is required, not cosmetic: Pydantic v2 puts the exception object
        # itself into ctx.error, which JSONResponse cannot serialise on its own — same trap
        # 04-constraints.md documents for the framework's own RequestValidationError handler.
        raise AppException(
            422,
            "VALIDATION_FAILED",
            "Invalid column mapping",
            {"errors": jsonable_encoder(exc.errors())},
        ) from exc


def _to_preview_out(outcome: importer.ImportOutcome) -> ImportPreviewOut:
    return ImportPreviewOut(
        row_count=outcome.row_count,
        imported_count=outcome.imported_count,
        already_imported_count=outcome.already_imported_count,
        skipped_count=outcome.skipped_count,
        errors=outcome.errors,
        new_sites=outcome.new_sites,
        new_gliders=outcome.new_gliders,
        new_harnesses=outcome.new_harnesses,
        new_categories=outcome.new_categories,
    )


@router.post("/columns", response_model=ImportColumnsOut)
def get_columns(
    file: UploadFile = File(...),
    sheet: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> ImportColumnsOut:
    data = _read_upload(file)
    try:
        sheet_names = importer.list_sheet_names(file.filename or "", data)
        columns = importer.read_columns(file.filename or "", data, sheet)
    except importer.SpreadsheetError as exc:
        raise AppException(422, "VALIDATION_FAILED", str(exc)) from exc
    logger.info(
        "Import columns read: %s sheet=%s, %d columns, by %s",
        file.filename,
        sheet,
        len(columns),
        current_user.id,
    )
    return ImportColumnsOut(columns=columns, sheet_names=sheet_names)


@router.post("/preview", response_model=ImportPreviewOut)
def preview_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    sheet: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportPreviewOut:
    data = _read_upload(file)
    field_mapping = _parse_mapping(mapping)
    try:
        outcome = importer.run_import(
            db, current_user.id, file.filename or "", data, field_mapping, commit=False, sheet=sheet
        )
    except importer.SpreadsheetError as exc:
        raise AppException(422, "VALIDATION_FAILED", str(exc)) from exc
    logger.info(
        "Import preview: %s sheet=%s, %d/%d importable, by %s",
        file.filename,
        sheet,
        outcome.imported_count,
        outcome.row_count,
        current_user.id,
    )
    return _to_preview_out(outcome)


@router.post("/commit", response_model=ImportCommitOut, status_code=201)
def commit_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    sheet: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportCommitOut:
    data = _read_upload(file)
    field_mapping = _parse_mapping(mapping)
    try:
        outcome = importer.run_import(
            db, current_user.id, file.filename or "", data, field_mapping, commit=True, sheet=sheet
        )
    except importer.SpreadsheetError as exc:
        raise AppException(422, "VALIDATION_FAILED", str(exc)) from exc
    logger.info(
        "Import committed: run=%s %s, %d/%d imported, by %s",
        outcome.import_run_id,
        file.filename,
        outcome.imported_count,
        outcome.row_count,
        current_user.id,
    )
    return ImportCommitOut(
        **_to_preview_out(outcome).model_dump(), import_run_id=outcome.import_run_id
    )


@router.get("", response_model=list[ImportRunOut])
def list_import_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImportRunOut]:
    rows = (
        db.execute(
            select(ImportRun)
            .where(ImportRun.owner_id == current_user.id)
            .order_by(ImportRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ImportRunOut.model_validate(row) for row in rows]


@router.delete("/{run_id}", response_model=ImportUndoOut)
def undo_import_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportUndoOut:
    run = _get_own_import_run(run_id, current_user, db)
    outcome = importer.undo_import(db, run)
    logger.info("Import run undone: %s by %s", run_id, current_user.id)
    return ImportUndoOut(**outcome.__dict__)
