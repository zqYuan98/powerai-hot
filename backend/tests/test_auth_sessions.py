"""Security configuration, signed session, and authentication contract tests."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.config import Settings
from core.session import decode_session, encode_session, validate_security_config


WORKSPACE_TOKEN = "workspace-access-token-1234567890"
ADMIN_TOKEN = "admin-access-token-12345678901234"
SECRET = base64.urlsafe_b64encode(b"s" * 32).decode()
APP_ORIGIN = "http://127.0.0.1:3010"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_token", "w" * 23),
        ("admin_token", "a" * 23),
    ],
)
def test_security_config_requires_24_character_access_tokens(field, value):
    values = {
        "workspace_token": WORKSPACE_TOKEN,
        "admin_token": ADMIN_TOKEN,
        "session_secret": SECRET,
        "session_ttl_seconds": 28800,
    }
    values[field] = value

    with pytest.raises(ValueError, match="24"):
        validate_security_config(**values)


def test_security_config_rejects_same_tokens():
    with pytest.raises(ValueError, match="differ"):
        validate_security_config(
            workspace_token="w" * 24,
            admin_token="w" * 24,
            session_secret=SECRET,
            session_ttl_seconds=28800,
        )


@pytest.mark.parametrize("secret", ["not base64!", base64.urlsafe_b64encode(b"short").decode()])
def test_security_config_requires_32_decoded_base64url_bytes(secret):
    with pytest.raises(ValueError, match="Base64URL|32"):
        validate_security_config(
            workspace_token=WORKSPACE_TOKEN,
            admin_token=ADMIN_TOKEN,
            session_secret=secret,
            session_ttl_seconds=28800,
        )


@pytest.mark.parametrize("matching_field", ["workspace_token", "admin_token"])
def test_security_config_rejects_secret_reused_as_access_token(matching_field):
    values = {
        "workspace_token": WORKSPACE_TOKEN,
        "admin_token": ADMIN_TOKEN,
        "session_secret": SECRET,
        "session_ttl_seconds": 28800,
    }
    values[matching_field] = SECRET

    with pytest.raises(ValueError, match="differ"):
        validate_security_config(**values)


def test_security_config_rejects_example_values():
    with pytest.raises(ValueError, match="example|default|placeholder"):
        validate_security_config(
            workspace_token="workspace-token-change-me-now",
            admin_token=ADMIN_TOKEN,
            session_secret=SECRET,
            session_ttl_seconds=28800,
        )


@pytest.mark.parametrize("ttl", [0, -1, True])
def test_security_config_requires_real_positive_session_ttl(ttl):
    with pytest.raises(ValueError, match="positive integer"):
        validate_security_config(
            workspace_token=WORKSPACE_TOKEN,
            admin_token=ADMIN_TOKEN,
            session_secret=SECRET,
            session_ttl_seconds=ttl,
        )


def test_settings_can_be_constructed_before_explicit_security_validation():
    candidate = Settings(
        workspace_token="",
        admin_token="",
        session_secret="",
    )

    assert candidate.workspace_token == ""
    assert candidate.admin_token == ""
    assert candidate.session_secret == ""


def test_signed_session_preserves_role_and_timestamps():
    cookie = encode_session("workspace", SECRET, now=100, ttl=3600)

    assert decode_session(cookie, SECRET, now=101) == {
        "v": 1,
        "role": "workspace",
        "iat": 100,
        "exp": 3700,
    }


def test_signed_session_rejects_expired_cookie():
    cookie = encode_session("admin", SECRET, now=100, ttl=10)

    assert decode_session(cookie, SECRET, now=110) is None


@pytest.mark.parametrize(
    "cookie",
    ["", "missing-dot", ".", "bad.payload.signature", "!!!.???"],
)
def test_signed_session_rejects_malformed_cookie(cookie):
    assert decode_session(cookie, SECRET, now=101) is None


def test_signed_session_rejects_role_tamper():
    cookie = encode_session("workspace", SECRET, now=100, ttl=3600)
    payload, signature = cookie.rsplit(".", 1)
    raw = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    raw["role"] = "admin"
    changed = base64.urlsafe_b64encode(
        json.dumps(raw, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    tampered = changed + "." + signature

    assert decode_session(tampered, SECRET, now=101) is None


def test_signed_session_requires_integer_version_one():
    raw = json.dumps(
        {"v": True, "role": "workspace", "iat": 100, "exp": 3700},
        separators=(",", ":"),
    ).encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    key = base64.urlsafe_b64decode(SECRET)
    signature = base64.urlsafe_b64encode(
        hmac.new(key, payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")

    assert decode_session(f"{payload}.{signature}", SECRET, now=101) is None


def test_lifespan_rejects_invalid_security_before_startup(monkeypatch):
    import asyncio
    import main

    calls: list[str] = []
    monkeypatch.setattr(main.settings, "workspace_token", "")
    monkeypatch.setattr(main.settings, "admin_token", ADMIN_TOKEN)
    monkeypatch.setattr(main.settings, "session_secret", SECRET)
    monkeypatch.setattr(main, "init_db", lambda: calls.append("init_db"))
    monkeypatch.setattr(main, "start_monitor", lambda: calls.append("start_monitor"))

    async def enter_lifespan():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(ValueError, match="24"):
        asyncio.run(enter_lifespan())

    assert calls == []


def test_lifespan_rejects_invalid_ttl_before_startup(monkeypatch):
    import asyncio
    import main

    calls: list[str] = []
    monkeypatch.setattr(main.settings, "workspace_token", WORKSPACE_TOKEN)
    monkeypatch.setattr(main.settings, "admin_token", ADMIN_TOKEN)
    monkeypatch.setattr(main.settings, "session_secret", SECRET)
    monkeypatch.setattr(main.settings, "session_ttl_seconds", 0)
    monkeypatch.setattr(main, "init_db", lambda: calls.append("init_db"))
    monkeypatch.setattr(main, "start_monitor", lambda: calls.append("start_monitor"))

    async def enter_lifespan():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(ValueError, match="positive integer"):
        asyncio.run(enter_lifespan())

    assert calls == []


@pytest.fixture()
def security_settings(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "workspace_token", WORKSPACE_TOKEN)
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)
    monkeypatch.setattr(settings, "session_secret", SECRET)
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    monkeypatch.setattr(settings, "session_ttl_seconds", 28800)
    monkeypatch.setattr(settings, "app_origin", APP_ORIGIN)
    monkeypatch.setattr(settings, "workspace_name", "Test Workspace")
    monkeypatch.setattr(settings, "workspace_subtitle", "Internal intelligence")
    return settings


@pytest.fixture()
def anonymous_client(security_settings):
    from main import app

    client = TestClient(
        app,
        base_url="https://testserver",
        raise_server_exceptions=False,
    )
    yield client
    client.close()


def unlock(client: TestClient, scope: str, token: str, *, origin: str = APP_ORIGIN):
    return client.post(
        "/api/auth/session",
        json={"scope": scope, "token": token},
        headers={"Origin": origin},
    )


@pytest.mark.parametrize(
    ("scope", "token"),
    [("workspace", WORKSPACE_TOKEN), ("admin", ADMIN_TOKEN)],
)
def test_session_unlock_requires_exact_scope_token_pair(anonymous_client, scope, token):
    response = unlock(anonymous_client, scope, token)

    assert response.status_code == 200
    assert response.json()["role"] == scope


@pytest.mark.parametrize(
    ("scope", "token"),
    [("admin", WORKSPACE_TOKEN), ("workspace", ADMIN_TOKEN)],
)
def test_session_unlock_rejects_cross_scope_token(anonymous_client, scope, token):
    response = unlock(anonymous_client, scope, token)

    assert response.status_code == 401
    assert token not in response.text


def test_session_cookie_has_strict_security_attributes(anonymous_client):
    response = unlock(anonymous_client, "admin", ADMIN_TOKEN)

    cookie = response.headers["set-cookie"].lower()
    assert "powerai_session=" in cookie
    assert "httponly" in cookie
    assert "path=/" in cookie
    assert "samesite=strict" in cookie
    assert "max-age=28800" in cookie
    assert "secure" in cookie


def test_session_cookie_omits_secure_when_disabled(anonymous_client, security_settings):
    security_settings.session_cookie_secure = False

    response = unlock(anonymous_client, "workspace", WORKSPACE_TOKEN)

    assert "secure" not in response.headers["set-cookie"].lower()


def test_get_session_returns_identity_without_access_codes(anonymous_client):
    assert unlock(anonymous_client, "admin", ADMIN_TOKEN).status_code == 200

    response = anonymous_client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "role": "admin",
        "mode": "shared",
        "workspace": {
            "name": "Test Workspace",
            "subtitle": "Internal intelligence",
        },
    }
    assert WORKSPACE_TOKEN not in response.text
    assert ADMIN_TOKEN not in response.text


def test_public_admin_mode_authenticates_anonymous_admin_requests(anonymous_client, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "access_mode", "public_admin")

    session = anonymous_client.get("/api/auth/session")
    admin = anonymous_client.get("/api/admin/config")

    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["role"] == "admin"
    assert session.json()["mode"] == "public_admin"
    assert admin.status_code == 200


def test_get_session_treats_bad_cookie_as_unauthenticated(anonymous_client):
    anonymous_client.cookies.set("powerai_session", "malformed")

    response = anonymous_client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert response.json()["role"] is None


def test_logout_clears_session_cookie(anonymous_client):
    assert unlock(anonymous_client, "workspace", WORKSPACE_TOKEN).status_code == 200

    response = anonymous_client.delete(
        "/api/auth/session", headers={"Origin": APP_ORIGIN}
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "powerai_session=" in cookie
    assert "max-age=0" in cookie
    assert anonymous_client.get("/api/auth/session").json()["authenticated"] is False


def test_logout_rejects_bad_origin_for_cookie_session(anonymous_client):
    assert unlock(anonymous_client, "workspace", WORKSPACE_TOKEN).status_code == 200

    response = anonymous_client.delete(
        "/api/auth/session", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert anonymous_client.get("/api/auth/session").json()["authenticated"] is True


def test_authenticated_session_switch_rejects_bad_origin(anonymous_client):
    assert unlock(anonymous_client, "workspace", WORKSPACE_TOKEN).status_code == 200

    response = unlock(
        anonymous_client,
        "admin",
        ADMIN_TOKEN,
        origin="https://evil.example",
    )

    assert response.status_code == 403
    assert anonymous_client.get("/api/auth/session").json()["role"] == "workspace"


def test_session_endpoint_defensively_returns_503_for_invalid_config(
    anonymous_client, security_settings
):
    security_settings.workspace_token = ""

    response = unlock(anonymous_client, "admin", ADMIN_TOKEN)

    assert response.status_code == 503


def test_session_endpoint_defensively_returns_503_for_invalid_ttl(
    anonymous_client, security_settings
):
    security_settings.session_ttl_seconds = 0

    response = unlock(anonymous_client, "admin", ADMIN_TOKEN)

    assert response.status_code == 503


def test_non_ascii_access_code_is_compared_without_server_error(
    anonymous_client, security_settings
):
    security_settings.workspace_token = "电" * 24

    response = unlock(anonymous_client, "workspace", "电" * 24)

    assert response.status_code == 200


@pytest.fixture()
def dependency_client(security_settings):
    from core.auth import require_admin, require_workspace

    probe = FastAPI()

    @probe.get("/workspace", dependencies=[Depends(require_workspace)])
    def workspace_only():
        return {"ok": True}

    @probe.post("/workspace", dependencies=[Depends(require_workspace)])
    def mutate_workspace():
        return {"ok": True}

    @probe.get("/admin", dependencies=[Depends(require_admin)])
    def admin_only():
        return {"ok": True}

    with TestClient(probe) as client:
        yield client


def _set_signed_cookie(client: TestClient, role: str):
    client.cookies.set("powerai_session", encode_session(role, SECRET, ttl=28800))


def test_admin_session_satisfies_workspace_dependency(dependency_client):
    _set_signed_cookie(dependency_client, "admin")

    assert dependency_client.get("/workspace").status_code == 200


def test_workspace_session_fails_admin_dependency_with_403(dependency_client):
    _set_signed_cookie(dependency_client, "workspace")

    assert dependency_client.get("/admin").status_code == 403


@pytest.mark.parametrize("path", ["/workspace", "/admin"])
def test_missing_authentication_is_401(dependency_client, path):
    assert dependency_client.get(path).status_code == 401


def test_cookie_authenticated_mutation_requires_exact_origin(dependency_client):
    _set_signed_cookie(dependency_client, "workspace")

    assert dependency_client.post("/workspace").status_code == 403
    assert dependency_client.post(
        "/workspace", headers={"Origin": "https://evil.example"}
    ).status_code == 403
    assert dependency_client.post(
        "/workspace", headers={"Origin": APP_ORIGIN}
    ).status_code == 200


def test_legacy_headers_remain_supported_without_origin(dependency_client):
    assert dependency_client.post(
        "/workspace", headers={"X-Workspace-Token": WORKSPACE_TOKEN}
    ).status_code == 200
    assert dependency_client.get(
        "/workspace", headers={"X-Admin-Token": ADMIN_TOKEN}
    ).status_code == 200
    assert dependency_client.get(
        "/admin", headers={"X-Admin-Token": ADMIN_TOKEN}
    ).status_code == 200
