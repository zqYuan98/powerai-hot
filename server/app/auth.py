"""管理员鉴权：口令登录 → HMAC 签名的 HttpOnly cookie。

前台内容匿名可读；写操作、后台设置与个人数据（收藏、笔记、商机跟进）只对管理员开放。
开发环境未设置 APP_PASSWORD 时视为管理员；生产环境启动时强制校验口令与密钥强度（见 config）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

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


def is_admin(request: Request) -> bool:
    return not auth_required() or verify_token(request.cookies.get(COOKIE_NAME))


async def admin_flag(request: Request) -> bool:
    return is_admin(request)


# 公开接口用它区分访客与管理员：访客看不到个人数据，也不会改动已读状态
Admin = Annotated[bool, Depends(admin_flag)]


async def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要管理员登录")
