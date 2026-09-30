"""知识库：公众号解析、标准号核验、质量门槛、去重、访客/管理员边界、知识信源、对 Agent 的接口。"""
from __future__ import annotations

import feedparser
import httpx
import pytest
import respx
from sqlalchemy import select

from app.collectors.http import PoliteClient
from app.config import settings
from app.core.ratelimit import SEARCH_LIMIT
from app.models import Article, Item, Job, Source
from app.pipeline import knowledge as kn
from app.pipeline.llm_schemas import KnowledgeOutput, KnowledgeScores

PASSWORD = "correct horse battery"
WX_URL = "https://mp.weixin.qq.com/s?__biz=MzA5&mid=2650&idx=1&sn=abc123&chksm=zz&scene=21#wechat_redirect"
WX_HTML = """<html><head><meta property="og:title" content="og 标题"></head><body>
<h1 id="activity-name"> 干货！GIS 安装的 8 个关键控制点，建议收藏 </h1>
<a id="js_name">送变电</a>
<div id="js_content" style="visibility: hidden;">
<p>GIS 安装前应检查基础预埋件水平误差不大于 2mm，依据 GB 50147—2010 第 5.2 条。</p>
<p>SF6 气体含水量交接试验值应小于 150μL/L，参照 GB50150-2016。</p>
<p>对接前必须清洁法兰面，环境湿度不宜超过 80%，并做好防尘棚。</p>
<script>var x = 1;</script></div>
<script>var ct = "1727578123";</script></body></html>"""
WX_BLOCKED = "<html><body><p>环境异常</p><p>完成验证后即可继续访问</p></body></html>"


def fake_output(**over: object) -> KnowledgeOutput:
    data: dict[str, object] = {
        "relevant": True, "is_promo": False, "title_zh": "GIS 安装的 8 个质量控制点",
        "summary": "总结 GIS 安装从基础到对接的关键控制点和验收指标。",
        "key_points": ["基础预埋件水平误差 ≤2mm", "SF6 含水量交接值 <150μL/L", "对接环境湿度 ≤80%"],
        "scenarios": "变电站 GIS 安装施工与监理", "solution_use": "施工组织设计的质量控制章节",
        "standards": ["GB 50147-2010", "GB 50150-2016", "DL/T 9999-2020"],
        "domain": "substation", "ktype": "construction", "tags": ["GIS", "SF6"],
        "scores": {"depth": 8, "practical": 9, "accuracy": 8, "originality": 6},
    }
    data.update(over)
    return KnowledgeOutput.model_validate(data)


@pytest.fixture
def fake_knowledge_llm(monkeypatch: pytest.MonkeyPatch) -> list[KnowledgeOutput]:
    """按顺序返回预置结果；列表为空时返回默认好文章。"""
    queue: list[KnowledgeOutput] = []

    async def fake_complete_json(*, task: str, **_: object) -> KnowledgeOutput:
        assert task == "knowledge"
        return queue.pop(0) if queue else fake_output()

    monkeypatch.setattr(kn, "complete_json", fake_complete_json)
    return queue


@pytest.fixture
def admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allow(url: str) -> None:  # 测试环境不做 DNS 解析
        return None

    from app.api import knowledge as api_knowledge
    monkeypatch.setattr(api_knowledge, "validate_public_url", allow)
    monkeypatch.setattr(settings, "app_password", PASSWORD)
    monkeypatch.setattr(settings, "public_base_url", "https://intel.example.com")
    SEARCH_LIMIT.reset()


# ---------- 纯函数 ----------

def test_article_key_ignores_wechat_tracking_params():
    clean = "https://mp.weixin.qq.com/s?__biz=MzA5&mid=2650&idx=1&sn=abc123"
    assert kn.article_key(WX_URL) == kn.article_key(clean)
    assert kn.article_key(clean) != kn.article_key(clean.replace("abc123", "def456"))
    assert kn.article_key("https://x.com/a?utm_source=wx") == kn.article_key("https://x.com/a")


def test_parse_wechat_article():
    got = kn.parse_wechat(WX_HTML)
    assert got.title.startswith("干货！GIS 安装") and got.account == "送变电"
    assert got.published_at is not None and got.published_at.year == 2024
    assert "水平误差不大于 2mm" in got.text and "var x" not in got.text
    assert got.text.count("\n") >= 2  # 段落保留

    with pytest.raises(kn.ArticleFetchError, match="环境异常"):
        kn.parse_wechat(WX_BLOCKED)


def test_ground_standards_keeps_only_codes_in_text():
    text = "依据 GB 50147—2010 第 5.2 条；参照 GB50150-2016。"
    assert kn.ground_standards(["GB 50147-2010", "GB 50150-2016", "DL/T 9999-2020", "GB"], text) == [
        "GB 50147-2010", "GB 50150-2016"]


def test_quality_gate():
    good = Article(title="t", content_text="GB 50147-2010", status="new")
    kn.apply_knowledge(good, fake_output())
    assert good.status == "analyzed" and good.score == pytest.approx(80.5)
    assert good.standards == ["GB 50147-2010"]

    promo = Article(title="t", content_text="", status="new")
    kn.apply_knowledge(promo, fake_output(is_promo=True))
    assert promo.status == "rejected" and promo.status_reason == "营销推广为主"

    news = Article(title="t", content_text="", status="new")
    kn.apply_knowledge(news, fake_output(relevant=False))
    assert news.status == "rejected"

    thin = Article(title="t", content_text="", status="new")
    kn.apply_knowledge(thin, fake_output(scores={"depth": 3, "practical": 4, "accuracy": 6, "originality": 3}))
    assert thin.status == "rejected" and "低于" in (thin.status_reason or "")
    assert kn.knowledge_score(KnowledgeScores(depth=10, practical=10, accuracy=10, originality=10)) == 100


# ---------- 数据库 ----------

async def login(api) -> None:
    assert (await api.post("/api/auth/login", json={"password": PASSWORD})).status_code == 200


async def run_jobs(session) -> None:
    ids = (await session.scalars(select(Job.payload["article_id"].as_integer()).where(Job.kind == "article_process")
                                 .order_by(Job.id))).all()
    async with PoliteClient(min_interval_s=0) as client:
        for aid in ids:
            await kn.process_article(session, client, aid)
    session.expire_all()


@pytest.mark.db
async def test_submit_process_and_visibility(session, api, admin_env, fake_knowledge_llm):
    assert (await api.post("/api/knowledge", json={"url": WX_URL})).status_code == 401  # 访客不能收录
    await login(api)
    r = await api.post("/api/knowledge", json={"url": WX_URL, "note": "给二期方案用"})
    assert r.status_code == 201 and r.json()["existed"] is False
    aid = r.json()["id"]
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://mp.weixin.qq.com/s").mock(return_value=httpx.Response(200, html=WX_HTML))
        await run_jobs(session)

    a = await session.get(Article, aid)
    assert a is not None and a.status == "analyzed" and a.account == "送变电"
    assert a.standards == ["GB 50147-2010", "GB 50150-2016"]  # 编造的 DL/T 9999 被丢弃
    # 同一篇文章换一种分享链接再收录：直接返回已有的
    again = await api.post("/api/knowledge", json={"url": WX_URL.replace("scene=21", "scene=126")})
    assert again.json() == {"id": aid, "existed": True, "status": "analyzed"}

    admin_detail = (await api.get(f"/api/knowledge/{aid}")).json()
    assert admin_detail["note"] == "给二期方案用" and "水平误差" in admin_detail["content_text"]

    api.cookies.clear()
    page = (await api.get("/api/knowledge", params={"domain": "substation"})).json()
    assert page["total"] == 1 and page["items"][0]["title"] == "GIS 安装的 8 个质量控制点"
    assert page["items"][0]["featured"] is True
    assert (await api.get("/api/knowledge", params={"q": "SF6"})).json()["total"] == 1
    assert (await api.get("/api/knowledge", params={"q": "不存在的词"})).json()["total"] == 0
    detail = (await api.get(f"/api/knowledge/{aid}")).json()
    assert detail["content_text"] is None and detail["note"] is None and detail["dims"]["practical"] == 9
    facets = (await api.get("/api/knowledge/facets")).json()
    assert facets["total"] == 1 and facets["status"] == {}
    assert next(d for d in facets["domains"] if d["key"] == "substation")["count"] == 1
    for method, path in (("PATCH", f"/api/knowledge/{aid}"), ("POST", f"/api/knowledge/{aid}/retry"),
                         ("DELETE", f"/api/knowledge/{aid}")):
        assert (await api.request(method, path, json={})).status_code == 401

    # 隐藏后访客看不到
    await login(api)
    assert (await api.patch(f"/api/knowledge/{aid}", json={"hidden": True})).json()["status"] == "hidden"
    api.cookies.clear()
    assert (await api.get(f"/api/knowledge/{aid}")).status_code == 404
    assert (await api.get("/api/knowledge")).json()["total"] == 0


@pytest.mark.db
async def test_blocked_page_then_paste_content(session, api, admin_env, fake_knowledge_llm):
    await login(api)
    aid = (await api.post("/api/knowledge", json={"url": WX_URL})).json()["id"]
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://mp.weixin.qq.com/s").mock(return_value=httpx.Response(200, html=WX_BLOCKED))
        await run_jobs(session)
    a = await session.get(Article, aid)
    assert a is not None and a.status == "failed" and "粘贴正文" in (a.status_reason or "")
    assert a.attempts == kn.MAX_ATTEMPTS  # 风控页不自动重试

    failed = (await api.get("/api/knowledge", params={"status": "failed"})).json()
    assert failed["total"] == 1  # 管理员能按状态查
    r = await api.post("/api/knowledge", json={"url": WX_URL, "title": "GIS 安装控制点",
                                               "content": "GIS 安装前应检查基础。\nGB 50147-2010 规定……"})
    assert r.json()["existed"] is True
    await session.execute(Job.__table__.delete())
    await session.commit()
    await session.refresh(a)
    assert a.status == "new" and a.attempts == 0
    await api.post(f"/api/knowledge/{aid}/retry")
    await run_jobs(session)
    a = await session.get(Article, aid)
    assert a is not None and a.status == "analyzed" and a.title == "GIS 安装控制点"


@pytest.mark.db
async def test_rejected_and_duplicate_are_hidden(session, api, admin_env, fake_knowledge_llm):
    await login(api)
    fake_knowledge_llm.extend([fake_output(), fake_output(is_promo=True), fake_output()])
    ids = []
    for n, title in enumerate(["GIS 安装要点", "限时特价资料包", "GIS 安装要点"]):
        r = await api.post("/api/knowledge", json={"url": f"https://example.com/a{n}", "title": title,
                                                   "content": "GIS 安装前应检查基础预埋件。GB 50147-2010"})
        ids.append(r.json()["id"])
    await run_jobs(session)
    statuses = [(await session.get(Article, i)).status for i in ids]  # type: ignore[union-attr]
    assert statuses == ["analyzed", "rejected", "duplicate"]
    dup = await session.get(Article, ids[2])
    assert dup is not None and dup.duplicate_of == ids[0]
    facets = (await api.get("/api/knowledge/facets")).json()
    assert facets["status"] == {"analyzed": 1, "rejected": 1, "duplicate": 1}
    # 管理员可以推翻模型判断
    assert (await api.patch(f"/api/knowledge/{ids[1]}", json={"hidden": False})).json()["status"] == "analyzed"
    assert (await api.delete(f"/api/knowledge/{ids[2]}")).status_code == 200


@pytest.mark.db
async def test_knowledge_source_goes_to_articles(session, fake_knowledge_llm, monkeypatch):
    from app.collectors import rss as rss_mod
    from app.worker.jobs import HANDLERS

    async def allow(url: str) -> None:
        return None

    monkeypatch.setattr(rss_mod, "validate_public_url", allow)

    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>送变电</title>
    <item><title>接地网降阻的五种做法</title><link>https://mp.weixin.qq.com/s/AbCdEf</link>
    <description>接地网降阻可以采用深井接地、外引接地、降阻剂等方式，依据 GB/T 50065-2011。</description>
    <pubDate>Mon, 28 Sep 2026 08:00:00 +0800</pubDate></item></channel></rss>"""
    source = Source(key="wx-sbd", name="送变电", kind="rss", url="https://rss.example.com/sbd.xml",
                    tier="T1_5", category="tech", config={"target": "knowledge"})
    session.add(source)
    await session.commit()
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://rss.example.com/sbd.xml").mock(return_value=httpx.Response(200, text=rss))
        async with PoliteClient(min_interval_s=0) as client:
            out = await HANDLERS["collect"](session, client, {"source_id": source.id})
    assert out["knowledge"] is True and out["new_ids"] == 1, out
    assert (await session.scalars(select(Item))).all() == []  # 不进资讯流
    await run_jobs(session)
    a = (await session.scalars(select(Article))).one()
    assert a.account == "送变电" and a.status == "analyzed" and a.source_id == source.id


@pytest.mark.db
async def test_related_to_item_and_agent_access(session, api, admin_env, fake_knowledge_llm):
    await login(api)
    r = await api.post("/api/knowledge", json={"url": "https://example.com/gis", "title": "GIS 安装",
                                               "content": "GIS 安装前应检查基础预埋件。GB 50147-2010"})
    aid = r.json()["id"]
    await run_jobs(session)
    api.cookies.clear()

    # 向量：给文章和一条商机造两个相近的向量，另一条商机造一个无关的
    a = await session.get(Article, aid)
    assert a is not None
    a.embedding = [1.0] + [0.0] * 1023
    src = Source(key="t", name="测试", kind="rss", url="https://t.example.com", tier="T1", category="tender")
    session.add(src)
    await session.flush()
    near = Item(source_id=src.id, tier="T1", url="https://t.example.com/1", url_hash="1", title="GIS 采购",
                status="analyzed", embedding=[0.9, 0.3] + [0.0] * 1022)
    far = Item(source_id=src.id, tier="T1", url="https://t.example.com/2", url_hash="2", title="食堂",
               status="analyzed", embedding=[0.0, 1.0] + [0.0] * 1022)
    session.add_all([near, far])
    await session.commit()
    assert [k["id"] for k in (await api.get("/api/knowledge/related", params={"item_id": near.id})).json()] == [aid]
    assert (await api.get("/api/knowledge/related", params={"item_id": far.id})).json() == []

    v1 = (await api.get("/api/v1/knowledge", params={"ktype": "construction"})).json()
    assert v1["total"] == 1 and v1["items"][0]["url"] == f"https://intel.example.com/knowledge/{aid}"
    assert v1["items"][0]["source_url"] == "https://example.com/gis" and "note" not in v1["items"][0]
    parsed = feedparser.parse((await api.get("/feed/knowledge.xml")).text)
    assert parsed.bozo == 0 and parsed.entries[0].link.endswith(f"/knowledge/{aid}")

    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "knowledge", "arguments": {"q": "GIS", "domain": "substation"}}}
    result = (await api.post("/api/mcp", json=call)).json()["result"]
    assert result["isError"] is False and "GB 50147-2010" in result["content"][0]["text"]
    assert result["structuredContent"]["total"] == 1
