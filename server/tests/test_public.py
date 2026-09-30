"""公开上线：访客与管理员的边界、访客反馈、给 Agent 的 REST API v1 / RSS / llms.txt / MCP。"""
from __future__ import annotations

import feedparser
import pytest
import respx
from fastapi import HTTPException
from sqlalchemy import select

from app.collectors.http import PoliteClient
from app.config import settings
from app.core.ratelimit import FEEDBACK_LIMIT, SEARCH_LIMIT, RateLimiter
from app.models import Item, Job
from app.pipeline.collect import collect_source
from app.pipeline.process import process_items
from tests.test_integration import fake_llm, mock_ccgp, seed_ccgp  # noqa: F401

PASSWORD = "correct horse battery"


@pytest.fixture
def admin_password(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "app_password", PASSWORD)
    monkeypatch.setattr(settings, "public_base_url", "https://intel.example.com")
    FEEDBACK_LIMIT.reset()
    SEARCH_LIMIT.reset()
    return PASSWORD


async def seed_items(session) -> tuple[int, int]:
    """跑一遍采集 + 处理；返回（无人机招标 id，被规则淘汰的食堂 id）。"""
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            await process_items(session, client, out.new_ids)
    uav = (await session.scalars(select(Item.id).where(Item.title.contains("无人机")))).one()
    canteen = (await session.scalars(select(Item.id).where(Item.title.contains("食堂")))).one()
    return uav, canteen


async def login(api) -> None:
    assert (await api.post("/api/auth/login", json={"password": PASSWORD})).status_code == 200


pytestmark = pytest.mark.db


async def test_visitor_reads_without_private_data(session, fake_llm, api, admin_password):  # noqa: F811
    uav, canteen = await seed_items(session)
    await login(api)
    await api.patch(f"/api/items/{uav}", json={"starred": True, "note": "只给自己看"})
    await api.patch(f"/api/leads/{uav}", json={"follow_status": "following", "follow_note": "已联系张工"})
    api.cookies.clear()

    assert (await api.get("/api/auth/me")).json() == {"admin": False, "auth_required": True}
    feed = (await api.get("/api/items", params={"view": "selected"})).json()["items"]
    card = next(c for c in feed if c["id"] == uav)
    assert card["starred"] is False and card["read"] is False
    assert card["lead"]["follow_status"] == "new" and card["lead"]["follow_note"] is None
    detail = (await api.get(f"/api/items/{uav}")).json()
    assert detail["note"] is None and detail["lead"]["bid_no"] == "GW-2026-0931"
    session.expire_all()
    assert (await session.get(Item, uav)).read_at is None  # 访客查看不改已读

    # 个人视图、被淘汰的条目、写操作与后台都要管理员
    assert (await api.get("/api/items", params={"view": "starred"})).status_code == 401
    assert (await api.get("/api/items", params={"view": "screened"})).status_code == 401
    assert (await api.get(f"/api/items/{canteen}")).status_code == 404
    assert (await api.patch(f"/api/items/{uav}", json={"starred": False})).status_code == 401
    assert (await api.patch(f"/api/leads/{uav}", json={"follow_status": "ignored"})).status_code == 401
    assert (await api.post("/api/digests/daily/generate", params={"period_start": "2026-09-29"})).status_code == 401
    for path in ("/api/sources", "/api/tuning", "/api/jobs", "/api/gold/stats", "/api/feedback"):
        assert (await api.get(path)).status_code == 401, path
    # 访客按跟进状态筛选无效，仍返回未忽略的全部
    assert (await api.get("/api/leads", params={"follow": "following"})).json()["total"] == 2

    by_ids = (await api.get("/api/items/by-ids", params={"ids": [uav, 999999, canteen]})).json()
    assert [c["id"] for c in by_ids] == [uav]
    assert (await api.get("/api/meta")).status_code == 200


async def test_visitor_search_is_rate_limited(session, api, admin_password, monkeypatch):
    monkeypatch.setattr(SEARCH_LIMIT, "limit", 2)
    for _ in range(2):
        assert (await api.get("/api/items/search", params={"q": "无人机"})).status_code == 200
    r = await api.get("/api/items/search", params={"q": "无人机"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    await login(api)
    assert (await api.get("/api/items/search", params={"q": "无人机"})).status_code == 200  # 管理员不限


def test_rate_limiter_window():
    limiter = RateLimiter(2, 60)
    limiter.check("a", now=0)
    limiter.check("a", now=1)
    limiter.check("b", now=1)
    with pytest.raises(HTTPException) as exc:
        limiter.check("a", now=30)
    assert exc.value.status_code == 429 and exc.value.headers == {"Retry-After": "30"}
    limiter.check("a", now=61)  # 第一次已滑出窗口


async def test_feedback_flow(session, api, admin_password, monkeypatch):
    monkeypatch.setattr(settings, "feishu_webhook_url", "https://open.feishu.cn/hook/x")
    assert (await api.post("/api/site/feedback", json={"content": " "})).status_code == 422
    r = await api.post("/api/site/feedback", json={"content": "希望增加江苏的招标源", "contact": "a@b.c",
                                                   "page_url": "/leads"}, headers={"user-agent": "pytest"})
    assert r.status_code == 201
    fid = r.json()["id"]
    job = (await session.scalars(select(Job).where(Job.kind == "feedback_notify"))).one()
    assert job.payload == {"feedback_id": fid}

    await login(api)
    rows = (await api.get("/api/feedback")).json()
    assert rows[0]["content"] == "希望增加江苏的招标源" and rows[0]["user_agent"] == "pytest"
    assert (await api.patch(f"/api/feedback/{fid}", json={"status": "done"})).json()["status"] == "done"
    assert (await api.get("/api/feedback", params={"status": "new"})).json() == []

    api.cookies.clear()
    for _ in range(4):
        assert (await api.post("/api/site/feedback", json={"content": "再来一条"})).status_code == 201
    assert (await api.post("/api/site/feedback", json={"content": "再来一条"})).status_code == 429


async def test_feedback_notify_job(session, monkeypatch):
    from app.models import Feedback
    from app.worker import jobs

    sent: list[str] = []

    async def fake_send(text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(jobs, "send_feishu", fake_send)
    fb = Feedback(content="日报能不能早点发", contact="wx:abc")
    session.add(fb)
    await session.commit()
    assert await jobs.HANDLERS["feedback_notify"](session, None, {"feedback_id": fb.id}) == {"sent": True}  # type: ignore[arg-type]
    assert "日报能不能早点发" in sent[0] and "wx:abc" in sent[0] and "/settings/feedback" in sent[0]


async def test_v1_rss_and_llms(session, fake_llm, api, admin_password):  # noqa: F811
    uav, _ = await seed_items(session)
    await login(api)
    await api.patch(f"/api/leads/{uav}", json={"follow_note": "内部备注"})
    api.cookies.clear()

    page = (await api.get("/api/v1/items", params={"window": "7d"})).json()
    item = next(i for i in page["items"] if i["id"] == uav)
    assert item["url"] == f"https://intel.example.com/items/{uav}"
    assert item["source_url"].startswith("http://www.ccgp.gov.cn/")
    assert item["lead"]["amount_wan"] == 1280.5 and "follow_note" not in item["lead"]
    assert (await api.get("/api/v1/items", params={"limit": 51})).status_code == 422
    leads = (await api.get("/api/v1/leads", params={"min_voltage_kv": 220})).json()
    assert leads["total"] == 1 and leads["items"][0]["lead"]["voltage_kv"] == 500
    assert (await api.get("/api/v1/hot")).status_code == 200
    assert (await api.get("/api/v1/dailies/latest")).status_code == 404
    assert (await api.get("/api/v1/search", params={"q": "无人机"})).json()[0]["id"] == uav

    spec = (await api.get("/api/v1/openapi.json")).json()
    assert "/api/v1/items" in spec["paths"] and "/api/sources" not in spec["paths"]
    assert spec["servers"] == [{"url": "https://intel.example.com"}]

    r = await api.get("/feed.xml")
    assert r.headers["content-type"].startswith("application/rss+xml")
    assert r.headers["access-control-allow-origin"] == "*" and "public" in r.headers["cache-control"]
    parsed = feedparser.parse(r.text)
    assert parsed.bozo == 0 and len(parsed.entries) == 2
    uav_entry = next(e for e in parsed.entries if e.link.endswith(f"/items/{uav}"))
    assert "1280.5 万元" in uav_entry.description and "内部备注" not in r.text
    assert (await api.get("/feed.xml", headers={"If-None-Match": r.headers["etag"]})).status_code == 304
    assert len(feedparser.parse((await api.get("/feed/leads.xml")).text).entries) == 2
    assert len(feedparser.parse((await api.get("/feed/channel/tender.xml")).text).entries) == 2
    assert (await api.get("/feed/channel/nope.xml")).status_code == 422
    assert feedparser.parse((await api.get("/feed/daily.xml")).text).bozo == 0

    llms = (await api.get("/llms.txt")).text
    assert "https://intel.example.com/api/mcp" in llms and "{base}" not in llms and "/stories/{id}" in llms

    pre = await api.options("/api/v1/items", headers={"Origin": "https://x.dev",
                                                      "Access-Control-Request-Method": "GET"})
    assert pre.status_code == 204 and pre.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-origin" not in (await api.get("/api/items")).headers  # 站内接口不开放跨域


async def rpc(api, method: str, params: dict | None = None, mid: int = 1) -> dict:
    r = await api.post("/api/mcp", json={"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
    assert r.status_code == 200
    return r.json()


async def test_mcp_server(session, fake_llm, api, admin_password):  # noqa: F811
    uav, _ = await seed_items(session)

    init = await rpc(api, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                         "clientInfo": {"name": "t", "version": "0"}})
    assert init["result"]["protocolVersion"] == "2025-03-26"
    assert init["result"]["capabilities"]["tools"] == {"listChanged": False}
    newer = await rpc(api, "initialize", {"protocolVersion": "2099-01-01"})
    assert newer["result"]["protocolVersion"] == "2025-06-18"
    note = await api.post("/api/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202

    tools = (await rpc(api, "tools/list"))["result"]["tools"]
    assert {t["name"] for t in tools} == {"latest", "search", "leads", "hot", "story", "daily", "knowledge"}
    assert all(t["inputSchema"]["type"] == "object" and t["annotations"]["readOnlyHint"] for t in tools)

    latest = (await rpc(api, "tools/call", {"name": "latest", "arguments": {"window": "7d"}}))["result"]
    assert latest["isError"] is False and "无人机" in latest["content"][0]["text"]
    assert any(i["id"] == uav for i in latest["structuredContent"]["items"])

    leads = (await rpc(api, "tools/call", {"name": "leads", "arguments": {"min_amount_wan": 1000}}))["result"]
    assert "1280.5 万元" in leads["content"][0]["text"] and leads["structuredContent"]["total"] == 1

    bad = (await rpc(api, "tools/call", {"name": "latest", "arguments": {"limit": 99}}))["result"]
    assert bad["isError"] is True and "limit" in bad["content"][0]["text"]
    missing = (await rpc(api, "tools/call", {"name": "story", "arguments": {"story_id": 424242}}))["result"]
    assert missing["isError"] is True and "不存在" in missing["content"][0]["text"]
    daily = (await rpc(api, "tools/call", {"name": "daily", "arguments": {}}))["result"]
    assert daily["isError"] is True

    assert (await rpc(api, "tools/call", {"name": "nope"}))["error"]["code"] == -32602
    assert (await rpc(api, "resources/list"))["error"]["code"] == -32601
    batch = (await api.post("/api/mcp", json=[{"jsonrpc": "2.0", "id": 7, "method": "ping"},
                                              {"jsonrpc": "2.0", "method": "notifications/initialized"}])).json()
    assert batch == [{"jsonrpc": "2.0", "id": 7, "result": {}}]
    assert (await api.post("/api/mcp", content=b"{not json")).status_code == 400
    assert (await api.get("/api/mcp")).status_code == 405
