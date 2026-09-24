"""Workspace/admin route access contract."""

from types import SimpleNamespace

import pytest

from conftest import WORKSPACE_TOKEN
from models import schema


BUSINESS_ROUTES = [
    "/api/articles",
    "/api/reports",
    "/api/cards",
    "/api/subscriptions",
]


@pytest.mark.parametrize("path", BUSINESS_ROUTES)
def test_anonymous_business_reads_require_authentication(anonymous_client, path):
    assert anonymous_client.get(path).status_code == 401


@pytest.mark.parametrize("path", BUSINESS_ROUTES)
def test_workspace_can_read_business_routes(client, path):
    assert client.get(path).status_code == 200


def test_source_management_list_is_admin_only(client, admin_client):
    assert client.get("/api/sources").status_code == 403
    assert admin_client.get("/api/sources").status_code == 200


@pytest.mark.parametrize("path", BUSINESS_ROUTES)
def test_admin_satisfies_workspace_access(admin_client, path):
    assert admin_client.get(path).status_code == 200


def test_missing_authentication_on_admin_route_is_401(anonymous_client):
    assert anonymous_client.get("/api/admin/scoring").status_code == 401


def test_workspace_on_admin_route_is_403(client):
    assert client.get("/api/admin/scoring").status_code == 403


def test_admin_can_access_admin_route(admin_client):
    assert admin_client.get("/api/admin/scoring").status_code == 200


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/cards/999/retry", None),
        ("/api/reports/topic", {"topic": "grid operations"}),
        ("/api/reports/999/retry", None),
        ("/api/admin/digest", None),
        ("/api/admin/weekly", None),
        ("/api/admin/crawl", {}),
    ],
)
def test_workspace_cannot_invoke_high_cost_operations(client, path, body):
    response = client.post(path, json=body) if body is not None else client.post(path)

    assert response.status_code == 403


def test_sliding_window_limiter_uses_injected_clock_and_bounds_keys():
    from core.rate_limit import SlidingWindowLimiter

    now = [0.0]
    limiter = SlidingWindowLimiter(
        limit=2,
        window_seconds=10,
        max_keys=2,
        clock=lambda: now[0],
    )

    assert limiter.allow("digest", "client-a") is True
    assert limiter.allow("digest", "client-a") is True
    assert limiter.allow("digest", "client-a") is False
    assert limiter.allow("weekly", "client-a") is True

    now[0] = 10.0
    assert limiter.allow("digest", "client-a") is True
    assert limiter.allow("crawl", "client-b") is True
    assert limiter.tracked_keys <= 2


def test_session_unlock_is_rate_limited_by_client(anonymous_client):
    for _ in range(5):
        response = anonymous_client.post(
            "/api/auth/session",
            json={"scope": "workspace", "token": WORKSPACE_TOKEN + "-wrong"},
        )
        assert response.status_code == 401

    assert anonymous_client.post(
        "/api/auth/session",
        json={"scope": "workspace", "token": WORKSPACE_TOKEN + "-wrong"},
    ).status_code == 429


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/cards/{card_id}/retry", None),
        ("/api/reports/topic", {"topic": "grid operations"}),
        ("/api/reports/{report_id}/retry", None),
        ("/api/admin/digest", None),
        ("/api/admin/weekly", None),
        ("/api/admin/crawl", {}),
    ],
)
def test_high_cost_operations_are_rate_limited(
    admin_client, db, monkeypatch, path, body
):
    from api import admin, cards, reports
    import services.digest as digest_service
    import services.research as research_service

    article = schema.Article(title="Rate limit seed", url="https://example.com/rate")
    db.add(article)
    db.flush()
    card = schema.KnowledgeCard(article_id=article.id)
    report = schema.Report(type="topic", title="Rate limit report", topic="grid")
    db.add_all([card, report])
    db.commit()

    monkeypatch.setattr(cards, "generate_card", lambda _card_id: None)
    monkeypatch.setattr(reports, "generate_topic", lambda _report_id: None)
    monkeypatch.setattr(reports, "generate_weekly", lambda _report_id: None)
    monkeypatch.setattr(
        reports,
        "create_topic",
        lambda _db, topic: SimpleNamespace(
            id=101, title=f"Topic: {topic}", status="生成中"
        ),
    )
    monkeypatch.setattr(
        digest_service,
        "build_daily_digest",
        lambda _db: SimpleNamespace(
            id=102, title="Digest", content_json={"total": 0}
        ),
    )
    monkeypatch.setattr(
        research_service,
        "create_weekly",
        lambda _db: SimpleNamespace(id=103, title="Weekly", status="生成中"),
    )
    monkeypatch.setattr(research_service, "generate_weekly", lambda _report_id: None)

    class FakeThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(admin, "threading", SimpleNamespace(Thread=FakeThread))
    monkeypatch.setattr(admin, "_crawl_state", dict(admin._crawl_state))
    admin._crawl_state.update(status="idle", stats=None, error=None)

    resolved_path = path.format(card_id=card.id, report_id=report.id)
    for _ in range(3):
        response = (
            admin_client.post(resolved_path, json=body)
            if body is not None
            else admin_client.post(resolved_path)
        )
        assert response.status_code == 200

    response = (
        admin_client.post(resolved_path, json=body)
        if body is not None
        else admin_client.post(resolved_path)
    )
    assert response.status_code == 429
