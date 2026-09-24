import pytest

from models import schema


@pytest.fixture()
def seeded(db):
    db.add_all([
        schema.Article(title="资讯1", channel="行业动态", kind="资讯", scored=True,
                       tier="T2", dim_scores={"relevance": 50}, relevance_score=35),
        schema.Article(title="论文1", channel="前沿论文", kind="论文", scored=True, tier="T1",
                       meta={"arxiv_id": "1", "title_zh": "论文一"},
                       dim_scores={"firsthand": 80, "relevance": 90, "utility": 60,
                                   "impact": 50, "depth": 70},
                       relevance_score=73, curated=True),
        schema.Source(name="arXiv", url="https://arxiv.org", status="已采纳",
                      tier="T1", last_status="ok"),
    ])
    db.commit()


def test_articles_kind_filter(client, seeded):
    rows = client.get("/api/articles?kind=论文").json()["items"]
    assert len(rows) == 1 and rows[0]["kind"] == "论文"
    assert rows[0]["meta"]["title_zh"] == "论文一"
    assert rows[0]["tier"] == "T1"
    assert rows[0]["crawled_at"]  # 时间窗筛选依赖：入库时间必有（server_default）


def test_channels_include_new(client, seeded):
    names = [c["name"] for c in client.get("/api/articles/channels").json()]
    assert names == ["行业动态", "国网规划", "招标公告", "AI洞察", "政策法规",
                     "前沿论文", "大模型动态", "落地案例"]


def test_scoring_get_put_roundtrip(admin_client, seeded):
    cfg = admin_client.get("/api/admin/scoring").json()
    assert cfg["hot_score"] == 80
    r = admin_client.put("/api/admin/scoring", json={"hot_score": 90})
    assert r.status_code == 200 and r.json()["hot_score"] == 90
    assert admin_client.put("/api/admin/scoring", json={"nope": 1}).status_code == 400


def test_scoring_recompute(admin_client, seeded, db):
    admin_client.put("/api/admin/scoring", json={
        "channel_thresholds": {"前沿论文": 80, "行业动态": 60, "国网规划": 60, "招标公告": 60,
                               "AI洞察": 60, "政策法规": 60, "大模型动态": 60, "落地案例": 60}})
    stats = admin_client.post("/api/admin/scoring/recompute").json()
    assert stats["recomputed"] >= 1
    paper = db.query(schema.Article).filter_by(kind="论文").one()
    db.refresh(paper)
    assert paper.curated is False  # 73 < 80


def test_crawl_async_start_and_status(admin_client, monkeypatch):
    """立即采集为异步：POST 立即返回 started，状态经 /crawl/status 轮询到 done。"""
    import time
    from api import admin

    monkeypatch.setattr(admin, "ingest_once", lambda db, **kw: {
        "fetched": 3, "inserted": 2, "curated": 1, "skipped_duplicate": 0,
        "prefiltered_out": 0, "analyze_errors": 0, "collector_errors": [], "samples": [],
    })

    class FakeSession:
        def close(self): pass
    import models.database as md
    monkeypatch.setattr(md, "SessionLocal", FakeSession)
    # 隔离并复位共享状态，避免测试间串扰
    monkeypatch.setattr(admin, "_crawl_state", dict(admin._crawl_state))
    admin._crawl_state.update(status="idle", stats=None, error=None)

    r = admin_client.post("/api/admin/crawl", json={"limit": 5}).json()
    assert r["status"] in ("started", "running")
    for _ in range(50):  # 后台线程极快（stub），轮询到 done 为止
        st = admin_client.get("/api/admin/crawl/status").json()
        if st["status"] == "done":
            break
        time.sleep(0.05)
    assert st["status"] == "done" and st["stats"]["inserted"] == 2
    assert st["stats"]["provider"]  # 附带模型标识


def test_crawl_rejects_concurrent_run(admin_client, monkeypatch):
    from api import admin
    monkeypatch.setattr(admin, "_crawl_state", dict(admin._crawl_state))
    admin._crawl_state.update(status="running", started_at="2026-07-08T00:00:00")
    r = admin_client.post("/api/admin/crawl", json={}).json()
    assert r["status"] == "running"  # 已有一轮在跑：不重复启动、不重复烧模型钱


def test_sources_health(admin_client, seeded):
    rows = admin_client.get("/api/admin/sources/health").json()
    arxiv = next(r for r in rows if r["name"] == "arXiv")
    assert arxiv["tier"] == "T1" and arxiv["last_status"] == "ok"


def test_sources_builtin_and_crawlable_flags(admin_client, seeded, db):
    db.add(schema.Source(name="机器之心", url="https://www.jiqizhixin.com/rss",
                         type="RSS", status="已采纳", tier="T2"))
    db.commit()
    rows = admin_client.get("/api/sources").json()
    arxiv = next(r for r in rows if r["name"] == "arXiv")
    rss = next(r for r in rows if r["name"] == "机器之心")
    # 内置标记来自 services/ingest.py 的 BUILTIN_SOURCE_NAMES；内置源本身按调度抓取，
    # 不走 build_collectors 的 DB 源分支，crawlable 只描述 DB 源
    assert arxiv["builtin"] is True
    assert rss["builtin"] is False and rss["crawlable"] is True


OPML = """<opml version="2.0"><body>
  <outline text="AI 分组">
    <outline text="示例源A" type="rss" xmlUrl="https://a.example.com/feed.xml"/>
    <outline title="示例源B" type="rss" xmlUrl="https://b.example.com/rss"/>
    <outline text="重复URL" type="rss" xmlUrl="https://a.example.com/feed.xml"/>
    <outline text="本地文件" type="rss" xmlUrl="file:///etc/passwd"/>
  </outline>
</body></opml>"""


@pytest.fixture()
def dns_open(monkeypatch):
    """example.com 子域在测试环境解析不了，会被 SSRF 防护 fail-closed 拦下；
    放开 IP 黑名单（scheme 校验仍生效，file:// 照样被拒）。"""
    from core import urlguard
    monkeypatch.setattr(urlguard, "_is_blocked_ip", lambda host: False)


def test_opml_import(admin_client, seeded, dns_open):
    r = admin_client.post("/api/sources/import-opml", json={"opml": OPML}).json()
    # 2 个有效新源；同 URL 去重记 skipped；file:// 被 URL 校验拦下记 errors
    assert r["imported"] == 2 and r["skipped"] == 1 and len(r["errors"]) == 1
    rows = admin_client.get("/api/sources").json()
    a = next(x for x in rows if x["name"] == "示例源A")
    assert a["status"] == "待审核" and a["type"] == "RSS"
    # 再导一遍：全部按已有 URL/名称去重，一个不加
    r2 = admin_client.post("/api/sources/import-opml", json={"opml": OPML}).json()
    assert r2["imported"] == 0 and r2["skipped"] == 3


def test_opml_import_active_and_bad_xml(admin_client, seeded, dns_open):
    opml = '<opml><body><outline text="直采源" xmlUrl="https://c.example.com/feed"/></body></opml>'
    r = admin_client.post("/api/sources/import-opml", json={"opml": opml, "active": True}).json()
    assert r["imported"] == 1
    row = next(x for x in admin_client.get("/api/sources").json() if x["name"] == "直采源")
    assert row["status"] == "已采纳" and row["crawlable"] is True
    assert admin_client.post("/api/sources/import-opml", json={"opml": "not xml"}).status_code == 400


def test_sources_mine_excludes_admin_added(admin_client, seeded):
    admin_client.post("/api/sources?active=true",
                json={"name": "管理员加的源", "url": "https://a.example.com", "type": "网站"})
    admin_client.post("/api/sources",
                json={"name": "我提报的源", "url": "https://b.example.com", "type": "网站"})
    mine = [r["name"] for r in admin_client.get("/api/sources?mine=true").json()]
    assert "我提报的源" in mine and "管理员加的源" not in mine
