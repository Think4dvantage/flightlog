"""JWT fail-closed behaviour, the typed error envelope, and health."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from flightlog.api.errors import code_for_status
from flightlog.config import AuthConfig
from flightlog.services.auth import (
    TokenError,
    decode_token,
    hash_password,
    verify_password,
)

# ---- JWT must fail closed at startup ----


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "too-short",
        "0123456789012345678901234567890",  # 31 chars — one below the floor
        "change-me",
        "CHANGE_ME_openssl_rand_hex_32",
    ],
)
def test_startup_refuses_a_weak_or_placeholder_secret(secret):
    with pytest.raises(RuntimeError):
        AuthConfig(jwt_secret=secret).validate_secret()


def test_startup_accepts_a_proper_secret():
    AuthConfig(jwt_secret="x" * 32).validate_secret()


# ---- password hashing ----


def test_password_round_trip():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong", hashed)


def test_user_without_a_password_never_authenticates():
    """A NULL hash means OAuth-only or not-yet-set — never 'any password works'."""
    assert not verify_password("anything", None)
    assert not verify_password("anything", "")


def test_password_over_bcrypt_limit_is_rejected():
    """bcrypt truncates at 72 bytes; silently accepting longer input collides passwords."""
    with pytest.raises(ValueError):
        hash_password("a" * 73)


# ---- token typing ----


def test_decode_rejects_a_token_of_the_wrong_type(patch_config):
    from flightlog.services.auth import create_refresh_token

    token = create_refresh_token("user-1")
    with pytest.raises(TokenError):
        decode_token(token, "access")


def test_decode_rejects_garbage(patch_config):
    with pytest.raises(TokenError):
        decode_token("not.a.jwt", "access")


# ---- error envelope ----


def test_status_to_code_mapping():
    assert code_for_status(400) == "VALIDATION_FAILED"
    assert code_for_status(401) == "AUTH_REQUIRED"
    assert code_for_status(403) == "PERMISSION_DENIED"
    assert code_for_status(404) == "ENTITY_NOT_FOUND"
    assert code_for_status(409) == "CONFLICT"
    assert code_for_status(422) == "VALIDATION_FAILED"
    assert code_for_status(500) == "INTERNAL_ERROR"
    assert code_for_status(418) == "ERROR"


async def test_every_error_uses_the_typed_envelope(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401

    body = r.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    # Not RFC 7807 — these keys must never appear.
    assert "type" not in body["error"]
    assert "title" not in body["error"]


async def test_validation_error_reports_422_and_does_not_500(client):
    """
    Pydantic v2 puts the exception object into ctx.error. Without jsonable_encoder the
    handler 500s while trying to report the 422 — this is that regression.
    """
    r = await client.post("/api/auth/login", json={"email": "not-an-email"})

    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_FAILED"
    assert isinstance(body["error"]["details"]["errors"], list)
    assert body["error"]["details"]["errors"]


async def test_unknown_route_returns_the_envelope(client):
    r = await client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ENTITY_NOT_FOUND"


# ---- timestamps ----


async def test_timestamps_are_serialised_with_an_explicit_utc_offset(client, make_token, make_user):
    """
    SQLite stores no offset, so a plain DateTime(timezone=True) returns a naive datetime
    and the API emits `2026-08-06T13:12:59.275499` — indistinguishable from local time.
    UtcDateTime re-attaches UTC on read. Pinned here because the VidFactory contract and
    every IGC timestamp depend on absolute UTC.
    """
    user = make_user(email="pilot@example.com")
    body = (await client.get("/api/auth/me", headers=make_token(user))).json()

    for field in ("created_at", "last_login_at"):
        value = body[field]
        if value is None:
            continue
        assert value.endswith("Z") or "+00:00" in value, f"{field} has no UTC marker: {value}"
        assert datetime.fromisoformat(value).utcoffset() == timedelta(0)


def test_utc_datetime_round_trips_through_sqlite(db_session):
    from flightlog.database.models import User

    user = User(
        email="tz@example.com", display_name="TZ", hashed_password=hash_password("pw12345678")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timedelta(0)


# ---- health ----


async def test_health_is_public_and_reports_subsystems(client):
    r = await client.get("/health")
    assert r.status_code == 200

    body = r.json()
    assert body["service"] == "flightlog"
    assert body["status"] == "ok"
    assert body["checks"]["sqlite"] == "ok"
    assert body["checks"]["igc_storage"] == "ok"
    assert isinstance(body["uptime_seconds"], int)
    assert body["version"]


async def test_health_degrades_without_503_when_igc_storage_is_missing(client, monkeypatch):
    """
    Unwritable IGC storage is degraded, not dead: the log still works, only uploads fail.
    Returning 503 would take the whole UI down and hide the actual problem.
    """
    monkeypatch.setattr("flightlog.api.routers.health._igc_storage_health", lambda: "not writable")

    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"


async def test_health_returns_503_when_the_database_is_down(client, monkeypatch):
    monkeypatch.setattr(
        "flightlog.api.routers.health.check_db_health",
        lambda _engine=None: "error: OperationalError",
    )

    r = await client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "error"
