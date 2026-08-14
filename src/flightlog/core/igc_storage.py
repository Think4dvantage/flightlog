"""
Content-addressed storage for uploaded IGC files — never a BLOB in the database
(architecture.md's IGC storage section).

    <storage.igc_dir>/<owner_id>/<upload_year>/<sha256>.igc

Sharded by the *upload* year, not the flight's own year: `libigc.Flight.create_from_file`
requires a real file on disk (specs/003-igc-ingest-analysis/research.md), so a file must be
written before it can be parsed to learn which year it actually flew in — sharding by upload
time avoids that ordering problem entirely. Content addressing (the sha256) is what gives
dedup and idempotent re-upload; the year folder is purely to avoid one flat directory, so
which year it lands in has no effect on correctness.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class IgcTooLargeError(Exception):
    """Raised when an uploaded file exceeds `storage.max_igc_bytes`."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_igc(igc_dir: str, owner_id: str, data: bytes, max_bytes: int) -> tuple[str, str]:
    """Validate size, hash, and write `data` to content-addressed storage.

    Returns (sha256, file_path). Idempotent — writing identical bytes for the same owner a
    second time is a no-op; the file already exists at the hash-derived path.
    """
    if len(data) > max_bytes:
        raise IgcTooLargeError(f"{len(data)} bytes exceeds the {max_bytes}-byte limit")

    digest = sha256_hex(data)
    path = Path(igc_dir) / owner_id / str(datetime.now(UTC).year) / f"{digest}.igc"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("IGC file written: %s (%d bytes)", path, len(data))
    else:
        logger.info("IGC file already on disk, reused: %s", path)
    return digest, str(path)


def read_igc(file_path: str) -> bytes:
    return Path(file_path).read_bytes()
