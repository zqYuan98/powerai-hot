"""共享测试夹具：内存 SQLite 会话，全程离线。"""
import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import settings
from models.database import Base
from models import schema  # noqa: F401  注册全部表


WORKSPACE_TOKEN = "workspace-test-access-0123456789"
ADMIN_TOKEN = "admin-test-access-01234567890123"
SESSION_SECRET = base64.urlsafe_b64encode(
    b"0123456789abcdef0123456789abcdef"
).decode()


@pytest.fixture(autouse=True)
def _force_stub_mode(monkeypatch):
    """强制离线 stub 模式。

    本机 backend/.env 配有真实 DEEPSEEK_API_KEY——不清空的话，"stub 模式"测试
    会打真实接口：断言变得不确定、跑得慢、还烧 API 额度。settings 是 lru_cache
    单例，patch 实例属性即可对所有读取方生效。
    """
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "embedding_api_key", "")
    monkeypatch.setattr(settings, "workspace_token", WORKSPACE_TOKEN)
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)
    monkeypatch.setattr(settings, "session_secret", SESSION_SECRET)
    from core.rate_limit import reset_rate_limits

    reset_rate_limits()


@pytest.fixture()
def db():
    # StaticPool + check_same_thread=False：TestClient 在工作线程中执行请求，
    # 需让所有线程共享同一个内存库连接（FastAPI 官方测试模式）。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def _test_client_factory(db):
    """Build API clients that share this test's dependency-overridden database."""
    from main import app
    from models.database import get_db

    app.dependency_overrides[get_db] = lambda: db
    clients: list[TestClient] = []

    def build(*, headers: dict[str, str] | None = None) -> TestClient:
        test_client = TestClient(app, headers=headers or {})
        clients.append(test_client)
        return test_client

    yield build

    for test_client in clients:
        test_client.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def anonymous_client(_test_client_factory):
    return _test_client_factory()


@pytest.fixture()
def client(_test_client_factory):
    return _test_client_factory(headers={"X-Workspace-Token": WORKSPACE_TOKEN})


@pytest.fixture()
def admin_client(_test_client_factory):
    return _test_client_factory(headers={"X-Admin-Token": ADMIN_TOKEN})
