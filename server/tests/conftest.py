"""测试基础设施。

数据库测试优先使用 TEST_DATABASE_URL（CI / Docker 中的 pgvector/pgvector:pg16）；
未设置时用 pgserver 在本机拉起一个临时 PostgreSQL 16 + pgvector（无需 Docker）。
每次测试会话新建一个数据库并执行真实的 Alembic 迁移。
"""
from __future__ import annotations

import os
import tempfile
import uuid
from argparse import Namespace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent
_DB_ERROR: str | None = None
_SKIP_TRGM = "0"


def _provision() -> str | None:
    """返回 asyncpg 连接串；无法获得数据库时返回 None。"""
    global _DB_ERROR, _SKIP_TRGM
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    try:
        import pgserver
    except ImportError:
        _DB_ERROR = "未设置 TEST_DATABASE_URL 且未安装 pgserver"
        return None
    try:
        srv = pgserver.get_server(Path(tempfile.gettempdir()) / "powerai-pg", cleanup_mode=None)
        name = f"powerai_test_{uuid.uuid4().hex[:8]}"
        srv.psql(f"CREATE DATABASE {name};")
    except Exception as exc:
        _DB_ERROR = f"pgserver 启动失败：{exc}"
        return None
    _SKIP_TRGM = "1"  # pgserver 不带 contrib 扩展
    parts = urlsplit(srv.get_uri())
    return urlunsplit(("postgresql+asyncpg", parts.netloc, f"/{name}", "", ""))


_URL = _provision()
os.environ.update({
    "ENV": "test",
    "DATABASE_URL": _URL or "postgresql+asyncpg://invalid@127.0.0.1:1/none",
    "APP_PASSWORD": "",
    "LLM_API_KEY": "",
    "EMBEDDING_API_KEY": "",
    "FEISHU_WEBHOOK_URL": "",
})


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _URL is not None:
        return
    skip = pytest.mark.skip(reason=_DB_ERROR or "没有可用的测试数据库")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: 需要 PostgreSQL 的集成测试")


@pytest.fixture(scope="session")
def migrated() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.cmd_opts = Namespace(x=[f"skip_trgm={_SKIP_TRGM}"])  # type: ignore[assignment]
    command.upgrade(cfg, "head")


TABLES = ("articles", "feedback", "gold_labels", "eval_runs", "notifications", "leads", "items", "stories",
          "source_runs", "sources", "watch_rules", "digests", "jobs", "llm_calls", "app_settings")


@pytest.fixture
async def api():
    import httpx

    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def session(migrated: None):
    from sqlalchemy import text

    from app.db import SessionLocal

    async with SessionLocal() as s:
        await s.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        await s.commit()
        yield s
