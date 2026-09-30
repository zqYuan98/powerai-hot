"""API 进程入口：uvicorn app.main:app

只读为主；写操作（采集、生成日报等）一律入队交给 worker，API 进程不跑后台任务。
前台内容匿名可读，写操作与后台只对管理员开放（见 auth.py）；/api/v1、/api/mcp、RSS 是给 Agent 的公开接口。
"""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import cache
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text

from app import auth
from app.api import digests, feeds, gold, items, knowledge, leads, mcp, site, stories, v1
from app.api import settings as settings_api
from app.config import settings
from app.db import SessionLocal, engine
from app.logs import setup_logging
from app.schemas.dto import LoginIn, Ok, Viewer


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
    # 站内接口的定义不对外；公开接口的定义见 /api/v1/openapi.json
    openapi_url="/api/openapi.json" if settings.env != "prod" else None,
)
PUBLIC_PREFIXES = ("/api/v1/", "/api/mcp", "/feed.xml", "/feed/", "/llms.txt")
ETAG_TYPES = ("application/json", "application/rss+xml", "text/plain")


@app.middleware("http")
async def etag_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """GET 的 JSON / RSS / 文本响应加弱 ETag，轮询时未变化返回 304。"""
    response = await call_next(request)
    if request.method != "GET" or response.status_code != 200 or \
            not response.headers.get("content-type", "").startswith(ETAG_TYPES):
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
    etag = 'W/"' + hashlib.blake2b(body, digest_size=12).hexdigest() + '"'
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    headers["etag"] = etag
    headers.setdefault("cache-control", "private, no-cache")  # RSS 等公开内容自带可共享缓存
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": headers["cache-control"]})
    return Response(content=body, status_code=200, headers=headers)


@app.middleware("http")
async def public_cors(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """公开接口允许任意来源的浏览器调用（匿名只读，不依赖 cookie）。"""
    if not request.url.path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    if request.method == "OPTIONS":
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, If-None-Match, Mcp-Protocol-Version, Mcp-Session-Id",
            "Access-Control-Max-Age": "86400",
        })
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "ETag, Retry-After"
    return response


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


@public.get("/me", response_model=Viewer)
async def me(request: Request) -> Viewer:
    return Viewer(admin=auth.is_admin(request), auth_required=auth.auth_required())


content = APIRouter(prefix="/api")
for module in (items, leads, stories, digests, knowledge, site, v1, mcp):
    content.include_router(module.router)

admin = APIRouter(prefix="/api", dependencies=[Depends(auth.require_admin)])
for router in (items.admin_router, leads.admin_router, digests.admin_router, knowledge.admin_router,
               site.admin_router, gold.router, settings_api.router):
    admin.include_router(router)

app.include_router(public)
app.include_router(content)
app.include_router(admin)
app.include_router(feeds.router)


@cache
def v1_schema() -> dict[str, Any]:
    """从完整定义里只挑出 /api/v1/ 路径及其引用到的模型。"""
    full = get_openapi(title=app.title, version=app.version, routes=app.routes)
    paths = {p: op for p, op in full["paths"].items() if p.startswith("/api/v1/")}
    schemas = full.get("components", {}).get("schemas", {})
    keep: set[str] = set()
    todo: list[Any] = [paths]
    while todo:
        node = todo.pop()
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and (name := ref.rsplit("/", 1)[-1]) not in keep:
                keep.add(name)
                todo.append(schemas[name])
            todo.extend(node.values())
        elif isinstance(node, list):
            todo.extend(node)
    return {
        "openapi": full["openapi"],
        "info": {"title": "电力基建情报站 公开 API", "version": "1.0.0",
                 "description": "匿名只读。标题与摘要由模型根据原文生成，关键信息请以 source_url 指向的原文为准。"},
        "paths": paths,
        "components": {"schemas": {k: schemas[k] for k in sorted(keep)}},
    }


@app.get("/api/v1/openapi.json", include_in_schema=False)
async def v1_openapi() -> dict[str, Any]:
    return {**v1_schema(), "servers": [{"url": settings.public_base_url.rstrip("/")}]}
