"""Authentication flow: registration gating, login, refresh, profile, password change."""

from __future__ import annotations

import pytest

import flightlog.config as _fl_config
from flightlog.database.models import User
from flightlog.services.auth import create_access_token, decode_token

from .conftest import TEST_PASSWORD, build_config

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"


async def test_register_returns_token_pair(client):
    r = await client.post(
        REGISTER,
        json={"email": "new@example.com", "display_name": "New", "password": "a-good-password"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600


async def test_register_normalises_email_case(client):
    await client.post(
        REGISTER,
        json={"email": "MiXeD@Example.COM", "display_name": "M", "password": "a-good-password"},
    )
    r = await client.post(LOGIN, json={"email": "mixed@example.com", "password": "a-good-password"})
    assert r.status_code == 200


async def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "display_name": "D", "password": "a-good-password"}
    assert (await client.post(REGISTER, json=payload)).status_code == 201

    r = await client.post(REGISTER, json=payload)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


async def test_register_rejects_short_password(client):
    r = await client.post(
        REGISTER,
        json={"email": "short@example.com", "display_name": "S", "password": "abc"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_register_blocked_when_self_registration_disabled(client, monkeypatch):
    monkeypatch.setattr(
        _fl_config, "_config", build_config(auth={"allow_self_registration": False})
    )

    r = await client.post(
        REGISTER,
        json={"email": "nope@example.com", "display_name": "N", "password": "a-good-password"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_registration_status_reflects_the_flag(client, monkeypatch):
    r = await client.get("/api/auth/registration-status")
    assert r.json() == {"self_registration": True}

    monkeypatch.setattr(
        _fl_config, "_config", build_config(auth={"allow_self_registration": False})
    )
    r = await client.get("/api/auth/registration-status")
    assert r.json() == {"self_registration": False}


async def test_login_succeeds(client, make_user):
    make_user(email="pilot@example.com")
    r = await client.post(LOGIN, json={"email": "pilot@example.com", "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_login_wrong_password_is_401(client, make_user):
    make_user(email="pilot@example.com")
    r = await client.post(LOGIN, json={"email": "pilot@example.com", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_login_unknown_account_is_indistinguishable_from_wrong_password(client, make_user):
    """A different status or message here would be an account-enumeration oracle."""
    make_user(email="pilot@example.com")

    wrong_pw = await client.post(
        LOGIN, json={"email": "pilot@example.com", "password": "wrong-password"}
    )
    no_account = await client.post(
        LOGIN, json={"email": "ghost@example.com", "password": "wrong-password"}
    )

    assert wrong_pw.status_code == no_account.status_code == 401
    assert wrong_pw.json() == no_account.json()


async def test_login_disabled_account_is_401(client, make_user):
    make_user(email="off@example.com", is_active=False)
    r = await client.post(LOGIN, json={"email": "off@example.com", "password": TEST_PASSWORD})
    assert r.status_code == 401


async def test_refresh_rotates_the_pair(client, make_user):
    make_user(email="pilot@example.com")
    login = await client.post(LOGIN, json={"email": "pilot@example.com", "password": TEST_PASSWORD})
    refresh_token = login.json()["refresh_token"]

    r = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_access_token_is_rejected_as_a_refresh_token(client, make_user):
    """The `type` claim is what stops a replayed access token from minting new ones."""
    make_user(email="pilot@example.com")
    login = await client.post(LOGIN, json={"email": "pilot@example.com", "password": TEST_PASSWORD})

    r = await client.post("/api/auth/refresh", json={"refresh_token": login.json()["access_token"]})
    assert r.status_code == 401


async def test_me_requires_authentication(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_me_returns_profile_without_the_password_hash(client, make_token, make_user):
    user = make_user(email="pilot@example.com", display_name="Ragnar")
    r = await client.get("/api/auth/me", headers=make_token(user))

    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "pilot@example.com"
    assert body["display_name"] == "Ragnar"
    assert body["role"] == "pilot"
    assert "hashed_password" not in body
    assert "password" not in body


async def test_me_rejects_a_garbage_token(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_update_me_applies_patch_semantics(client, make_token, make_user):
    user = make_user(email="pilot@example.com", display_name="Before")
    headers = make_token(user)

    r = await client.put("/api/auth/me", json={"display_name": "After"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "After"
    # Untouched fields keep their values rather than being reset to defaults.
    assert body["units"] == "metric"
    assert body["timezone"] == "Europe/Zurich"


async def test_change_password_requires_the_current_one(client, make_token, make_user):
    user = make_user(email="pilot@example.com")
    headers = make_token(user)

    bad = await client.post(
        "/api/auth/me/password",
        json={"current_password": "not-it", "password": "brand-new-password"},
        headers=headers,
    )
    assert bad.status_code == 401

    good = await client.post(
        "/api/auth/me/password",
        json={"current_password": TEST_PASSWORD, "password": "brand-new-password"},
        headers=headers,
    )
    assert good.status_code == 204

    assert (
        await client.post(
            LOGIN, json={"email": "pilot@example.com", "password": "brand-new-password"}
        )
    ).status_code == 200
    assert (
        await client.post(LOGIN, json={"email": "pilot@example.com", "password": TEST_PASSWORD})
    ).status_code == 401


@pytest.mark.parametrize("role", ["pilot", "admin"])
async def test_token_carries_the_role_claim(make_user, role):
    """require_admin reads `role` off the token; verify it survives the round trip."""
    user = make_user(email=f"{role}@example.com", role=role)
    payload = decode_token(create_access_token(user.id, user.role), "access")

    assert payload["sub"] == user.id
    assert payload["role"] == role
    assert payload["type"] == "access"


async def test_deactivated_user_with_a_valid_token_is_rejected(
    client, make_token, make_user, db_session
):
    """A token stays cryptographically valid after deactivation — is_active is the gate."""
    user = make_user(email="pilot@example.com")
    headers = make_token(user)
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 200

    db_session.query(User).filter(User.id == user.id).update({"is_active": False})
    db_session.commit()

    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
