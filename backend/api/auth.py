"""Create, inspect, and delete signed browser sessions."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from core.auth import (
    SESSION_COOKIE_NAME,
    constant_time_matches,
    ensure_security_config,
    is_public_admin_mode,
    require_cookie_origin,
    require_workspace,
)
from core.config import settings
from core.rate_limit import enforce_rate_limit
from core.session import decode_session, encode_session


router = APIRouter(prefix="/auth", tags=["auth"])


class SessionCreate(BaseModel):
    scope: Literal["workspace", "admin"]
    token: str


def _session_response(role: str | None) -> dict:
    return {
        "authenticated": role is not None,
        "role": role,
        "mode": settings.access_mode,
        "workspace": {
            "name": settings.workspace_name,
            "subtitle": settings.workspace_subtitle,
        },
    }


@router.post("/session")
def create_session(payload: SessionCreate, request: Request, response: Response):
    ensure_security_config()
    enforce_rate_limit(request, "auth.session", unlock=True)
    existing = decode_session(
        request.cookies.get(SESSION_COOKIE_NAME), settings.session_secret
    )
    if existing is not None:
        require_cookie_origin(request)

    expected = (
        settings.workspace_token if payload.scope == "workspace" else settings.admin_token
    )
    if not constant_time_matches(payload.token, expected):
        raise HTTPException(401, "Invalid access code")

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=encode_session(
            payload.scope,
            settings.session_secret,
            ttl=settings.session_ttl_seconds,
        ),
        max_age=settings.session_ttl_seconds,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return _session_response(payload.scope)


@router.get("/session")
def get_session(request: Request):
    ensure_security_config()
    if is_public_admin_mode():
        return _session_response("admin")
    session = decode_session(
        request.cookies.get(SESSION_COOKIE_NAME), settings.session_secret
    )
    role = str(session["role"]) if session is not None else None
    return _session_response(role)


@router.delete(
    "/session",
    status_code=204,
    dependencies=[Depends(require_workspace)],
)
def delete_session(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
