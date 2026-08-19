"""Pydantic schemas for self-service spreadsheet import (v0.9.8, specs/008-self-service-import)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from flightlog.core.spreadsheet_import import ALL_FIELDS, REQUIRED_FIELDS


class ImportColumnOut(BaseModel):
    name: str
    samples: list[str]


class ImportColumnsOut(BaseModel):
    columns: list[ImportColumnOut]
    # Empty for CSV. For Excel, every real worksheet — never assume the first one is the
    # right one; this pilot's own legacy workbook has six (architecture.md).
    sheet_names: list[str]


class ImportMappingIn(BaseModel):
    """{flightlog_field: source_column_header}. Sent as a JSON-encoded form field alongside the
    file, since multipart requests can't carry a nested JSON body directly."""

    mapping: dict[str, str]

    @field_validator("mapping")
    @classmethod
    def _validate_mapping(cls, v: dict[str, str]) -> dict[str, str]:
        unknown = set(v) - set(ALL_FIELDS)
        if unknown:
            raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
        missing = set(REQUIRED_FIELDS) - set(v)
        if missing:
            raise ValueError(f"Required field(s) not mapped: {', '.join(sorted(missing))}")
        return v


class ImportRowErrorOut(BaseModel):
    row: int
    reason: str


class ImportPreviewOut(BaseModel):
    row_count: int
    imported_count: int
    already_imported_count: int
    skipped_count: int
    errors: list[ImportRowErrorOut]
    new_sites: list[str]
    new_gliders: list[str]
    new_harnesses: list[str]
    new_categories: list[str]


class ImportCommitOut(ImportPreviewOut):
    import_run_id: str


class ImportRunOut(BaseModel):
    id: str
    source_filename: str
    row_count: int
    imported_count: int
    skipped_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportUndoOut(BaseModel):
    flights_deleted: int
    flights_kept: int
    sites_deleted: int
    gliders_deleted: int
    harnesses_deleted: int
    categories_deleted: int
    reference_rows_kept: int
