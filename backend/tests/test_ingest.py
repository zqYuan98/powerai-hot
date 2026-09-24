from collector.base import BaseCollector, RawArticle
from models import schema
from services import ingest as ingest_mod
from services.ingest import build_collectors, ingest_once


class FakeCollector(BaseCollector):
    source_name = "假信源"
    domain = "fake.cn"
    tier = "T1"

    def __init__(self, items):
        self._items = items

    def fetch(self):
        return self._items


class BoomCollector(BaseCollector):
    source_name = "坏信源"

    def fetch(self):
        raise RuntimeError("网络炸了")


class NamedCollector(FakeCollector):
    def __init__(self, source_name, items):
        super().__init__(items)
        self.source_name = source_name
        self.domain = f"{source_name}.example.com"


def test_max_total_caps_new_items(db, monkeypatch):
    """单次采集处理的新条目有上限，防止源过多压垮容器。"""
    _mock_analyzers(monkeypatch)
    items = [RawArticle(title=f"新闻{i}", url=f"http://fake.cn/{i}") for i in range(20)]
    stats = ingest_once(db, collectors=[FakeCollector(items)], max_total=5)
    assert stats["inserted"] == 5 and stats["capped"] is True
    assert db.query(schema.Article).count() == 5


def test_round_robin_prevents_one_source_from_consuming_the_run(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    collectors = [
        NamedCollector(
            name,
            [RawArticle(title=f"{name}-{i}", url=f"https://{name}.example.com/{i}") for i in range(5)],
        )
        for name in ("alpha", "beta", "gamma")
    ]

    stats = ingest_once(
        db,
        collectors=collectors,
        max_total=6,
        max_per_source=2,
        run_key="fairness:round-robin",
    )

    assert stats["inserted"] == 6
    counts = {
        source.name: len(source.articles)
        for source in db.query(schema.Source).filter(schema.Source.name.in_(("alpha", "beta", "gamma")))
    }
    assert counts == {"alpha": 2, "beta": 2, "gamma": 2}


def test_builtin_collector_source_is_not_registered_as_rss(db, monkeypatch):
    _mock_analyzers(monkeypatch)

    ingest_once(
        db,
        collectors=[FakeCollector([RawArticle(title="新闻", url="https://fake.cn/1")])],
        max_total=1,
        run_key="source-kind:builtin",
    )

    source = db.query(schema.Source).filter_by(name="假信源").one()
    assert source.type == "网站"
    assert source.submitted_by == "builtin"


def _mock_analyzers(monkeypatch, relevant=True):
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda title, content="": {"relevant": relevant,
                                                   "domain": "电力" if relevant else "无关",
                                                   "channel": None})
    monkeypatch.setattr(ingest_mod, "score", lambda title, content="": {
        "reason": "测试理由",
        "dims": {"firsthand": 80, "ai_relevance": 90, "power_relevance": 40, "utility": 60, "impact": 50, "depth": 70},
    })
    monkeypatch.setattr(ingest_mod, "enrich", lambda title, content="": {
        "title_zh": "", "summary": f"摘要:{title}", "tags": ["测试"], "org": "行业",
    })


def test_pipeline_scores_and_curates(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    c = FakeCollector([RawArticle(title="新闻A", url="http://fake.cn/a", channel="行业动态")])
    stats = ingest_once(db, collectors=[c])
    assert stats == {**stats, "fetched": 1, "inserted": 1, "curated": 1, "skipped_duplicate": 0}
    a = db.query(schema.Article).one()
    assert a.scored is True
    assert a.tier == "T1"
    assert a.dim_scores["ai_relevance"] == 90
    assert a.relevance_score == 66  # T1: 加权均值66 × 1.0
    assert a.curated is True and a.hot is False


def test_prefilter_reject_stored_unscored_with_noise_reason(db, monkeypatch):
    _mock_analyzers(monkeypatch, relevant=False)
    c = FakeCollector([RawArticle(title="无关内容", url="http://fake.cn/x")])
    stats = ingest_once(db, collectors=[c])
    a = db.query(schema.Article).one()
    assert a.scored is False and a.curated is False and a.relevance_score == 0
    assert a.noise_reason == "预筛判定无关（无关）"  # 噪音视图可回溯原因
    assert stats["prefiltered_out"] == 1


def test_dedup_by_url_hash(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    item = RawArticle(title="新闻A", url="http://fake.cn/a")
    ingest_once(db, collectors=[FakeCollector([item])], run_key="dedup:first")
    stats = ingest_once(db, collectors=[FakeCollector([item])], run_key="dedup:second")
    assert stats["skipped_duplicate"] == 1 and stats["inserted"] == 0


def test_collector_failure_isolated_and_health_recorded(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    db.add_all([
        schema.Source(name="坏信源", url="http://bad.cn", status="已采纳"),
        schema.Source(name="假信源", url="http://fake.cn", status="已采纳"),
    ])
    db.commit()
    good = FakeCollector([RawArticle(title="好新闻", url="http://fake.cn/ok")])
    stats = ingest_once(db, collectors=[BoomCollector(), good])
    assert stats["inserted"] == 1                       # 坏采集器不影响好采集器
    assert stats["collector_errors"] == ["坏信源"]
    bad_src = db.query(schema.Source).filter_by(name="坏信源").one()
    assert bad_src.last_status == "error" and "网络炸了" in bad_src.last_error
    good_src = db.query(schema.Source).filter_by(name="假信源").one()
    assert good_src.last_status == "ok" and good_src.last_crawled_at is not None


def test_analysis_failure_stores_unscored(db, monkeypatch):
    def boom(title, content=""):
        raise RuntimeError("LLM超时")
    monkeypatch.setattr(ingest_mod, "prefilter", boom)
    c = FakeCollector([RawArticle(title="新闻B", url="http://fake.cn/b")])
    stats = ingest_once(db, collectors=[c])
    a = db.query(schema.Article).one()
    assert a.scored is False and stats["analyze_errors"] == 1


def test_paper_meta_and_title_zh_saved(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda t, c="": {"relevant": True, "domain": "AI技术", "channel": "前沿论文"})
    monkeypatch.setattr(ingest_mod, "score", lambda title, content="": {
        "reason": "r",
        "dims": {"firsthand": 95, "ai_relevance": 88, "power_relevance": 60, "utility": 70, "impact": 60, "depth": 80},
    })
    monkeypatch.setattr(ingest_mod, "enrich", lambda title, content="": {
        "title_zh": "统一OCR模型", "summary": "s", "tags": [], "org": "arXiv",
    })
    item = RawArticle(title="UniOCR", url="http://arxiv.org/abs/1", channel="前沿论文",
                      kind="论文", meta={"arxiv_id": "1", "authors": ["A"]})
    ingest_once(db, collectors=[FakeCollector([item])])
    a = db.query(schema.Article).one()
    assert a.kind == "论文" and a.channel == "前沿论文"
    assert a.meta["arxiv_id"] == "1"
    assert a.meta["title_zh"] == "统一OCR模型"


def test_prefilter_channel_overrides_default(db, monkeypatch):
    """便宜模型给出的频道优先于采集器默认频道（分类只做一次）。"""
    _mock_analyzers(monkeypatch)
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda t, c="": {"relevant": True, "domain": "电力", "channel": "招标公告"})
    ingest_once(db, collectors=[FakeCollector([RawArticle(title="x", url="http://fake.cn/ch")])])
    assert db.query(schema.Article).one().channel == "招标公告"


def test_source_locked_channel_is_not_overridden_by_prefilter(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    monkeypatch.setattr(
        ingest_mod,
        "prefilter",
        lambda t, c="": {"relevant": True, "domain": "AI技术", "channel": "AI洞察"},
    )
    item = RawArticle(
        title="org/grid-vision",
        url="https://github.com/org/grid-vision",
        channel="落地案例",
        kind="案例",
        meta={"lock_channel": True},
    )

    ingest_once(db, collectors=[FakeCollector([item])], run_key="channel:locked")

    assert db.query(schema.Article).one().channel == "落地案例"


def test_enrich_failure_does_not_block_scoring(db, monkeypatch):
    """富化链失败：评分照常生效（并行链互不拖累）。"""
    _mock_analyzers(monkeypatch)
    def boom(title, content=""):
        raise RuntimeError("翻译挂了")
    monkeypatch.setattr(ingest_mod, "enrich", boom)
    stats = ingest_once(db, collectors=[FakeCollector([RawArticle(title="好新闻", url="http://fake.cn/e2")])])
    a = db.query(schema.Article).one()
    assert a.scored is True and a.relevance_score == 66 and a.summary is None
    assert stats["analyze_errors"] == 1


def test_score_failure_keeps_enrichment(db, monkeypatch):
    """评分链失败：摘要/译题照常入库，scored=False 可重试。"""
    _mock_analyzers(monkeypatch)
    def boom(title, content=""):
        raise RuntimeError("评分挂了")
    monkeypatch.setattr(ingest_mod, "score", boom)
    ingest_once(db, collectors=[FakeCollector([RawArticle(title="好新闻", url="http://fake.cn/s2")])])
    a = db.query(schema.Article).one()
    assert a.scored is True and a.scored_by == "rule" and a.summary is not None


def test_feishu_notify_on_curated_keyword_hit(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    db.add(schema.Subscription(user_id="me", keywords=["布控球"]))
    db.commit()
    monkeypatch.setattr(ingest_mod.settings, "feishu_webhook_url", "https://open.feishu.cn/hook/x")
    sent = {}
    monkeypatch.setattr(ingest_mod.httpx, "post",
                        lambda url, **kw: sent.update(url=url, **kw) or None)
    ingest_once(db, collectors=[FakeCollector([RawArticle(title="布控球新方案", url="http://fake.cn/f1")])])
    assert sent["url"].startswith("https://open.feishu.cn")
    assert "布控球新方案" in sent["json"]["content"]["text"]


def test_feishu_not_sent_without_webhook(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    db.add(schema.Subscription(user_id="me", keywords=["布控球"]))
    db.commit()
    called = []
    monkeypatch.setattr(ingest_mod.httpx, "post", lambda *a, **k: called.append(1))
    ingest_once(db, collectors=[FakeCollector([RawArticle(title="布控球新方案", url="http://fake.cn/f2")])])
    assert called == []  # 未配置 webhook 静默跳过


def test_build_collectors_group_filter(db):
    news = build_collectors(db, group="news")
    papers = build_collectors(db, group="papers")
    assert all(c.group == "news" for c in news)
    assert {c.source_name for c in papers} == {"arXiv", "Hugging Face Papers"}
    assert {c.source_name for c in build_collectors(db, group="all")} >= {
        "北极星电力网",
        "国家能源局",
        "国家电网",
        "南方电网",
        "中国政府采购网",
        "南方电网供应链",
        "arXiv",
    }
    # GitHub Trending（FrontierSnapshotCollector）2026-07-26 停用：43% 噪音、零精选，
    # 同类需求由 GitHubReleasesCollector 的 23 个人工挑定仓库覆盖。
    assert "GitHub Trending" not in {c.source_name for c in build_collectors(db, group="all")}


def test_build_collectors_does_not_recrawl_builtin_website_as_rss(db):
    db.add(schema.Source(
        name="AI HOT",
        url="https://aihot.virxact.com",
        type="RSS",
        status="已采纳",
        submitted_by="builtin",
    ))
    db.commit()

    names = [c.source_name for c in build_collectors(db, group="news")]

    assert names.count("AI HOT") == 1


def test_build_collectors_rss_gets_tier(db):
    db.add(schema.Source(name="OpenAI Blog", url="https://openai.com/blog/rss.xml",
                         type="RSS", status="已采纳", tier="T1"))
    db.commit()
    rss = [c for c in build_collectors(db, group="news") if c.source_name == "OpenAI Blog"]
    assert rss and rss[0].tier == "T1"


def test_dedup_within_single_run(db, monkeypatch):
    """同一批内重复 URL：session 关 autoflush，靠批内 seen 集合拦截。"""
    _mock_analyzers(monkeypatch)
    item = RawArticle(title="重复新闻", url="http://fake.cn/dup")
    stats = ingest_once(db, collectors=[FakeCollector([item, item])])
    assert stats["inserted"] == 1 and stats["skipped_duplicate"] == 1
    assert db.query(schema.Article).count() == 1


def test_concurrent_analysis_conflict_keeps_raw_articles(tmp_path, monkeypatch):
    """raw-first 后，模型阶段的并发唯一键冲突不能回滚已提交原始文章。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from models.database import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()

    item = RawArticle(title="并发新闻", url="http://fake.cn/race")
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda t, c="": {"relevant": True, "domain": "电力"})

    conflicted = False

    def score_and_conflict(title, content=""):
        # 首次评分期间另一会话抢先提交了同一条（模拟定时任务与手动采集并发）
        nonlocal conflicted
        if not conflicted:
            conflicted = True
            other = Session()
            other.add(schema.Article(title=title, url=item.url, url_hash=item.url_hash))
            other.commit()
            other.close()
        return {"reason": "r",
                "dims": {"firsthand": 50, "ai_relevance": 50, "power_relevance": 50, "utility": 50, "impact": 50, "depth": 50}}

    monkeypatch.setattr(ingest_mod, "score", score_and_conflict)
    monkeypatch.setattr(ingest_mod, "enrich", lambda title, content="": {
        "title_zh": "", "summary": "s", "tags": [], "org": "行业"})
    good = RawArticle(title="后续新闻", url="http://fake.cn/after")
    stats = ingest_once(db, collectors=[FakeCollector([item, good])])
    # 当前条已先提交；模型阶段的外部重复写失败不应删除原始内容，后续条也照常入库。
    assert stats["skipped_duplicate"] == 0
    assert stats["inserted"] == 2
    assert db.query(schema.Article).count() == 2
    db.close()


def test_ingest_clusters_similar_articles(db, monkeypatch):
    """两条相似内容归同簇，T1 当主条；embed 被 mock。

    注意：FakeCollector 本身 tier="T1"，先入库的媒体稿要用 T2 子类制造对比。"""
    _mock_analyzers(monkeypatch)
    monkeypatch.setattr(ingest_mod, "embed", lambda text: [1.0, 0.0])

    class T2Collector(FakeCollector):
        tier = "T2"
    t2 = RawArticle(title="媒体转述", url="http://fake.cn/m")
    ingest_once(db, collectors=[T2Collector([t2])], run_key="cluster:t2")

    t1 = RawArticle(title="官方发布", url="http://fake.cn/o")
    ingest_once(db, collectors=[FakeCollector([t1])], run_key="cluster:t1")  # FakeCollector tier T1

    arts = db.query(schema.Article).order_by(schema.Article.id).all()
    assert arts[0].cluster_id == arts[1].cluster_id
    assert arts[1].is_cluster_main is True and arts[0].is_cluster_main is False


def test_ingest_embed_failure_self_cluster(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    def boom(text):
        raise RuntimeError("embedding 接口挂了")
    monkeypatch.setattr(ingest_mod, "embed", boom)
    ingest_once(db, collectors=[FakeCollector([RawArticle(title="x", url="http://fake.cn/e")])])
    a = db.query(schema.Article).one()
    assert a.embedding is None and a.cluster_id == f"c{a.id}" and a.is_cluster_main is True


def test_ingest_sanitizes_and_stores_content_html(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    dirty = '<p>全文</p><script>alert(1)</script><img src="https://x/a.png" onerror="e()">'
    ingest_once(db, collectors=[FakeCollector([
        RawArticle(title="带全文的新闻", url="http://fake.cn/rich1", content="全文", content_html=dirty),
    ])])
    row = db.query(schema.Article).filter_by(url="http://fake.cn/rich1").one()
    assert row.content_html and "<p>全文</p>" in row.content_html
    assert "script" not in row.content_html and "onerror" not in row.content_html


def test_ingest_empty_content_html_stored_as_none(db, monkeypatch):
    _mock_analyzers(monkeypatch)
    ingest_once(db, collectors=[FakeCollector([
        RawArticle(title="纯摘要新闻", url="http://fake.cn/plain1", content="摘要"),
    ])])
    row = db.query(schema.Article).filter_by(url="http://fake.cn/plain1").one()
    assert row.content_html is None


def test_fulltext_backfills_content_before_scoring(db, monkeypatch):
    """正文回捞必须发生在评分之前，否则本轮 summary/评分仍只见标题。"""
    from collector import fulltext as fulltext_mod

    seen = {}

    def fake_fetch(url, **kwargs):
        seen["url"] = url
        return {"content": "正文内容" * 40, "content_html": "<p>正文</p>", "chars": 160}

    monkeypatch.setattr(fulltext_mod, "is_supported", lambda url: True)
    monkeypatch.setattr(ingest_mod.fulltext, "is_supported", lambda url: True)
    monkeypatch.setattr(ingest_mod.fulltext, "fetch_fulltext", fake_fetch)

    scored_with = {}

    def capture_score(title, content="", **kwargs):
        scored_with["content"] = content
        return {"dims": {k: 60 for k in ingest_mod.DIM_KEYS}, "reason": "r", "fallback": False}

    monkeypatch.setattr(ingest_mod, "score", capture_score)
    monkeypatch.setattr(ingest_mod, "enrich",
                        lambda *a, **k: {"title_zh": "", "summary": "s", "tags": [], "org": "o"})
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda *a, **k: {"relevant": True, "domain": "电力", "channel": None})

    article = schema.Article(title="标题", channel="行业动态", url="https://www.csg.cn/a.html",
                             url_hash="ft-hash", processing_status="pending")
    db.add(article)
    db.commit()

    ingest_mod.process_pending(db, limit=5)
    db.refresh(article)

    assert article.content.startswith("正文内容")
    assert (article.meta or {}).get("fulltext_status") == "ok"
    # 关键：评分拿到的是回捞后的正文，不是空串
    assert scored_with["content"].startswith("正文内容")
    assert seen["url"] == "https://www.csg.cn/a.html"


def test_fulltext_miss_is_recorded_and_does_not_block(db, monkeypatch):
    monkeypatch.setattr(ingest_mod.fulltext, "is_supported", lambda url: True)
    monkeypatch.setattr(ingest_mod.fulltext, "fetch_fulltext", lambda url, **k: None)
    monkeypatch.setattr(ingest_mod, "score",
                        lambda *a, **k: {"dims": {x: 60 for x in ingest_mod.DIM_KEYS}, "reason": "r", "fallback": False})
    monkeypatch.setattr(ingest_mod, "enrich",
                        lambda *a, **k: {"title_zh": "", "summary": "s", "tags": [], "org": "o"})
    monkeypatch.setattr(ingest_mod, "prefilter",
                        lambda *a, **k: {"relevant": True, "domain": "电力", "channel": None})

    article = schema.Article(title="标题2", channel="行业动态", url="https://www.csg.cn/b.html",
                             url_hash="ft-hash-2", processing_status="pending")
    db.add(article)
    db.commit()

    ingest_mod.process_pending(db, limit=5)
    db.refresh(article)

    assert (article.meta or {}).get("fulltext_status") == "miss"
    assert article.scored is True  # 回捞失败不阻断评分
