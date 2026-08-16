"""
API key minting, hashing and verification.

Format `flg_<prefix:8>_<secret:43>`: an 8-hex-char lookup prefix plus a 43-char
`secrets.token_urlsafe(32)` secret (02-backend-conventions.md, already decided). Looked up
by the indexed unique `key_prefix`, then verified with `hmac.compare_digest` against a
SHA-256 hash of the *full* presented key — not bcrypt: the secret is 256 bits of CSPRNG
output, not a guessable password, so bcrypt's slow-hash property buys nothing and would cost
real time on a bulk integration request.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PREFIX_BYTES = 4  # -> 8 hex chars


class MintedKey:
    """Returned once, at creation time. `plaintext` is never stored anywhere past this."""

    __slots__ = ("key_hash", "key_prefix", "plaintext")

    def __init__(self, plaintext: str, key_prefix: str, key_hash: str) -> None:
        self.plaintext = plaintext
        self.key_prefix = key_prefix
        self.key_hash = key_hash


def _hash(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def mint_key() -> MintedKey:
    key_prefix = secrets.token_hex(_PREFIX_BYTES)
    secret = secrets.token_urlsafe(32)
    plaintext = f"flg_{key_prefix}_{secret}"
    return MintedKey(plaintext=plaintext, key_prefix=key_prefix, key_hash=_hash(plaintext))


def parse_key_prefix(plaintext: str) -> str | None:
    """Extract the lookup prefix from a presented key, or None if malformed."""
    parts = plaintext.split("_", 2)
    if len(parts) != 3 or parts[0] != "flg" or len(parts[1]) != _PREFIX_BYTES * 2:
        return None
    return parts[1]


def verify_key(plaintext: str, key_hash: str) -> bool:
    """Constant-time comparison of the full presented key against the stored hash."""
    if parse_key_prefix(plaintext) is None:
        return False
    return hmac.compare_digest(_hash(plaintext), key_hash)
