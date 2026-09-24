"""Workspace/admin authentication dependencies for browsers and automation."""
from __future__ import annotations

import hmac

from fastapi import Cookie, Header, HTTPException, Request

from core.config import settings
from core.session import decode_session, validate_security_config


SESSION_COOKIE_NAME = "powerai_session"
_UNSAFE_METHODS = frozenset(("POST", "PUT", "PATCH", "DELETE"))


def is_public_admin_mode() -> bool:
    return settings.access_mode == "public_admin"


def ensure_security_config() -> None:
    """Fail closed when dependencies are called outside a validated lifespan."""
    try:
        validate_security_config(settings)
    except (TypeError, ValueError) as exc:
        raise HTTPException(503, "Authentication service is not configured") from exc


def constant_time_matches(candidate: str | None, expected: str) -> bool:
    """Compare configured text credentials safely, including non-ASCII values."""
    return isinstance(candidate, str) and hmac.compare_digest(
        candidate.encode("utf-8"), expected.encode("utf-8")
    )


def _header_role(
    x_workspace_token: str | None,
    x_admin_token: str | None,
) -> str | None:
    if constant_time_matches(x_admin_token, settings.admin_token):
        return "admin"
    if constant_time_matches(x_workspace_token, settings.workspace_token):
        return "workspace"
    return None


def require_cookie_origin(request: Request) -> None:
    """Enforce exact same-origin requests for cookie-authenticated mutations."""
    if request.method.upper() not in _UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if not constant_time_matches(origin, settings.app_origin):
        raise HTTPException(403, "Origin is not allowed")


def _cookie_role(request: Request, cookie: str | None) -> str | None:
    session = decode_session(cookie, settings.session_secret)
    if session is None:
        return None
    require_cookie_origin(request)
    return str(session["role"])


def require_workspace(
    request: Request,
    powerai_session: str | None = Cookie(default=None),
    x_workspace_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> str:
    """Allow workspace/admin sessions or either matching legacy header."""
    ensure_security_config()
    if is_public_admin_mode():
        return "admin"
    role = _header_role(x_workspace_token, x_admin_token)
    if role is not None:
        return role

    role = _cookie_role(request, powerai_session)
    if role is not None:
        return role
    raise HTTPException(401, "Authentication required")


def require_admin(
    request: Request,
    powerai_session: str | None = Cookie(default=None),
    x_workspace_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> str:
    """Allow only admin sessions or a matching legacy admin header."""
    ensure_security_config()
    if is_public_admin_mode():
        return "admin"
    role = _header_role(x_workspace_token, x_admin_token)
    if role is None:
        role = _cookie_role(request, powerai_session)
    if role == "admin":
        return role
    if role == "workspace":
        raise HTTPException(403, "Administrator access required")
    raise HTTPException(401, "Authentication required")
