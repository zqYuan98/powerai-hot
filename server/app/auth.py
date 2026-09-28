"""单用户鉴权：口令登录 → HMAC 签名的 HttpOnly cookie。

开发环境未设置 APP_PASSWORD 时免登录；生产环境启动时强制校验口令与密钥强度（见 config）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status

from app.config import settings

COOKIE_NAME = "pa_session"


def _sign(payload: str) -> str:
    mac = hmac.new(settings.session_key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def issue_token(now: int | None = None) -> str:
    exp = (now or int(time.time())) + settings.session_ttl_days * 86400
    payload = f"v1.{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str | None, now: int | None = None) -> bool:
    if not token or token.count(".") != 2:
        return False
    version, exp, sig = token.split(".")
    if version != "v1" or not exp.isdigit():
        return False
    if not hmac.compare_digest(sig, _sign(f"{version}.{exp}")):
        return False
    return int(exp) > (now or int(time.time()))


def check_password(password: str) -> bool:
    return bool(settings.app_password) and hmac.compare_digest(password.encode(), settings.app_password.encode())


def auth_required() -> bool:
    return bool(settings.app_password) or settings.env == "prod"


async def require_user(request: Request) -> None:
    if not auth_required():
        return
    if not verify_token(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
