"""API 进程入口：uvicorn app.main:app

只读为主；写操作（采集、生成日报等）一律入队交给 worker，API 进程不跑后台任务。
"""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import text

from app import auth
from app.api import digests, items, leads, stories
from app.api import settings as settings_api
from app.config import settings
from app.db import SessionLocal, engine
from app.logs import setup_logging
from app.schemas.dto import LoginIn, Ok


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    yield
    await engine.dispose()


app = FastAPI(
    title="电力基建情报站 API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.env != "prod" else None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def etag_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """GET JSON 响应加弱 ETag，前端轮询时未变化返回 304。"""
    response = await call_next(request)
    if request.method != "GET" or response.status_code != 200 or \
            not response.headers.get("content-type", "").startswith("application/json"):
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
    etag = 'W/"' + hashlib.blake2b(body, digest_size=12).hexdigest() + '"'
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    headers.update({"ETag": etag, "Cache-Control": "private, no-cache"})
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(content=body, status_code=200, headers=headers, media_type="application/json")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}


public = APIRouter(prefix="/api/auth", tags=["auth"])


@public.post("/login", response_model=Ok)
async def login(body: LoginIn, response: Response) -> Ok:
    if not auth.auth_required():
        return Ok(detail="开发环境未设置口令，免登录")
    if not auth.check_password(body.password):
        raise HTTPException(401, "口令错误")
    response.set_cookie(
        auth.COOKIE_NAME, auth.issue_token(), max_age=settings.session_ttl_days * 86400,
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
    )
    return Ok()


@public.post("/logout", response_model=Ok)
async def logout(response: Response) -> Ok:
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return Ok()


@public.get("/me", response_model=Ok)
async def me(request: Request) -> Ok:
    if auth.auth_required() and not auth.verify_token(request.cookies.get(auth.COOKIE_NAME)):
        raise HTTPException(401, "未登录")
    return Ok()


protected = APIRouter(prefix="/api", dependencies=[Depends(auth.require_user)])
for module in (items, leads, stories, digests, settings_api):
    protected.include_router(module.router)

app.include_router(public)
app.include_router(protected)
