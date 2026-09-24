from __future__ import annotations

from datetime import datetime, timezone
import threading

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from collector.base import BaseCollector, CollectorResult, RawArticle
from models.database import Base
from models import schema
from services import ingest as ingest_mod
from services.ingest import ingest_once


class ResultCollector(BaseCollector):
    source_name = "稳定信源"
    source_url = "https://stable.example/feed"
    domain = "stable.example"
    tier = "T1"

    def __init__(self, result):
        self._result = result

    def fetch(self):
        return self._result


def _raw(url: str = "https://stable.example/a") -> RawArticle:
    return RawArticle(
        title="OpenAI 发布电力巡检多模态模型",
        url=url,
        content="模型用于变电站巡检、OCR 和目标检测。",
        published_at=datetime(2026, 7, 17, 1, 2, 3, tzinfo=timezone.utc),
        source_external_id="item-1",
        provenance={"detail_url": f"{url}?detail=1", "attribution": "stable"},
    )


def test_job_run_and_source_run_record_status_and_run_key_idempotency(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "process_pending", lambda db, **kw: {"processed": 0, "model_count": 0, "fallback_model_count": 0, "rule_count": 0, "errors": 0})
    result = CollectorResult.ok(items=[_raw()])

    first = ingest_once(db, collectors=[ResultCollector(result)], run_key="news:2026-07-17T00", group="news")
    second = ingest_once(db, collectors=[ResultCollector(result)], run_key="news:2026-07-17T00", group="news")

    assert first["job_status"] == "ok"
    assert second["job_status"] == "skipped"
    assert db.query(schema.JobRun).filter_by(run_key="news:2026-07-17T00").count() == 1
    source_run = db.query(schema.SourceRun).one()
    assert source_run.transport_status == "ok"
    assert source_run.parse_status == "ok"
    assert source_run.fetched_count == 1


def test_new_articles_store_source_published_ingested_and_pending_before_ai(db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("primary model timed out")

    monkeypatch.setattr(ingest_mod, "prefilter", boom)
    stats = ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=[_raw()]))], run_key="news:raw-first")

    article = db.query(schema.Article).one()
    assert stats["inserted"] == 1
    assert article.source_id is not None
    assert article.published_at == datetime(2026, 7, 17, 1, 2, 3)
    assert article.ingested_at is not None
    assert article.processing_status == "processed"
    assert article.scored_by == "rule"
    assert article.summary


@pytest.mark.parametrize(
    ("result", "transport", "parse"),
    [
        (CollectorResult.ok(items=[]), "ok", "empty"),
        (CollectorResult.timeout("request timed out"), "timeout", "empty"),
        (CollectorResult.http_error(503, "upstream unavailable"), "http_error", "empty"),
        (CollectorResult.schema_error("missing items"), "ok", "schema_error"),
        (CollectorResult.parse_error("bad json"), "ok", "parse_error"),
    ],
)
def test_source_run_distinguishes_empty_transport_schema_and_parse(db, monkeypatch, result, transport, parse):
    monkeypatch.setattr(ingest_mod, "process_pending", lambda db, **kw: {"processed": 0, "model_count": 0, "fallback_model_count": 0, "rule_count": 0, "errors": 0})
    ingest_once(db, collectors=[ResultCollector(result)], run_key=f"news:{transport}:{parse}")
    source_run = db.query(schema.SourceRun).one()
    assert source_run.transport_status == transport
    assert source_run.parse_status == parse
    assert source_run.error_summary is None or len(source_run.error_summary) <= 500


def test_model_fallback_then_rule_scored_by_paths(db, monkeypatch):
    monkeypatch.setattr(ingest_mod.settings, "deepseek_api_key", "primary-key")
    monkeypatch.setattr(ingest_mod.settings, "custom_api_url", "https://custom.example/v1")
    monkeypatch.setattr(ingest_mod.settings, "custom_model", "fallback-model")

    def fake_prefilter(title, content="", *, provider=None):
        return {"relevant": True, "domain": "AI技术", "channel": "大模型动态"}

    calls = []

    def fake_score(title, content="", *, provider=None):
        calls.append(provider or "primary")
        if provider is None:
            raise RuntimeError("429")
        return {"reason": "fallback ok", "dims": {"firsthand": 90, "relevance": 90, "utility": 90, "impact": 90, "depth": 90}}

    monkeypatch.setattr(ingest_mod, "prefilter", fake_prefilter)
    monkeypatch.setattr(ingest_mod, "score", fake_score)
    monkeypatch.setattr(ingest_mod, "enrich", lambda title, content="", *, provider=None: {"title_zh": "", "summary": "摘要", "tags": [], "org": "AI"})

    ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=[_raw()]))], run_key="news:fallback")
    assert db.query(schema.Article).one().scored_by == "fallback_model"
    assert calls == ["primary", "primary", "primary", "custom"]

    db.query(schema.Article).delete()
    db.query(schema.JobRun).delete()
    db.query(schema.SourceRun).delete()
    db.commit()
    monkeypatch.setattr(ingest_mod.settings, "custom_api_url", "")

    def always_boom(title, content="", *, provider=None):
        raise RuntimeError("invalid json")

    monkeypatch.setattr(ingest_mod, "score", always_boom)
    ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=[_raw("https://stable.example/b")]))], run_key="news:rule")
    article = db.query(schema.Article).one()
    assert article.scored_by == "rule"
    assert article.processing_status == "processed"
    assert article.summary
    # 规则分不得自动进精选：旧实现在这里置 curated=True + quality=60，
    # 2026-07-24 模型故障期间精选池因此被灌满从未经模型评判的条目。
    assert article.curated is False


def test_health_checks_database_and_rss_is_public(db, client, anonymous_client):
    source = schema.Source(name="Public Feed", url="https://stable.example/feed", status="已采纳")
    db.add(source)
    db.flush()
    db.add(
        schema.Article(
            title="公开精选",
            url="https://stable.example/public",
            url_hash="public",
            summary="公开摘要",
            curated=True,
            scored=True,
            processing_status="processed",
            scored_by="rule",
            source_domain="stable.example",
            source_id=source.id,
        )
    )
    db.commit()

    assert anonymous_client.get("/health").status_code == 200
    rss = anonymous_client.get("/api/rss.xml")
    assert rss.status_code == 200
    assert "公开精选" in rss.text
    assert "scored_by" not in rss.text
    assert client.get("/api/system/status").status_code == 403


def test_web_lifespan_does_not_start_scheduler(monkeypatch):
    import main

    called = []
    monkeypatch.setattr(main, "start_monitor", lambda: called.append("started"))
    with TestClient(main.app):
        pass
    assert called == []


def test_default_run_key_uses_group_windows(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "_utcnow_naive", lambda: datetime(2026, 7, 17, 8, 59, 1))
    assert ingest_mod._default_run_key("ingest-news") == "ingest-news:2026-07-17T08"
    monkeypatch.setattr(ingest_mod, "_utcnow_naive", lambda: datetime(2026, 7, 17, 9, 59, 59))
    assert ingest_mod._default_run_key("ingest-news") == "ingest-news:2026-07-17T08"
    monkeypatch.setattr(ingest_mod, "_utcnow_naive", lambda: datetime(2026, 7, 17, 10, 0, 0))
    assert ingest_mod._default_run_key("ingest-news") == "ingest-news:2026-07-17T10"
    monkeypatch.setattr(ingest_mod, "_utcnow_naive", lambda: datetime(2026, 7, 17, 23, 59, 0))
    assert ingest_mod._default_run_key("ingest-papers") == "ingest-papers:2026-07-17"


def test_start_job_run_handles_concurrent_unique_race(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker():
        session = Session()
        try:
            barrier.wait()
            results.append(ingest_mod._start_job_run(session, "ingest-news", "news:race")[1])
        except Exception as exc:  # pragma: no cover - assertion reports concrete exception
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    check = Session()
    assert errors == []
    assert sorted(results) == [False, True]
    assert check.query(schema.JobRun).filter_by(run_key="news:race").count() == 1
    check.close()


def test_prefilter_timeout_uses_rule_prefilter_and_rule_score_without_keys(db, monkeypatch):
    monkeypatch.setattr(ingest_mod.settings, "deepseek_api_key", "")
    monkeypatch.setattr(ingest_mod.settings, "custom_api_url", "")

    def timeout(title, content=""):
        raise httpx.TimeoutException("prefilter timeout")

    monkeypatch.setattr(ingest_mod, "prefilter", timeout)
    monkeypatch.setattr(ingest_mod, "score", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no model")))
    monkeypatch.setattr(ingest_mod, "enrich", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no model")))

    ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=[_raw("https://stable.example/no-key")]))], run_key="news:no-key")

    article = db.query(schema.Article).one()
    assert article.processing_status == "processed"
    assert article.scored_by == "rule"
    assert article.scored is True
    assert article.summary
    assert article.curated is False  # 同上：无模型时不得伪造精选


def test_retry_model_call_retries_transient_but_not_format_errors(monkeypatch):
    calls = []
    sleeps = []

    def transient():
        calls.append("transient")
        if len(calls) < 3:
            raise httpx.TimeoutException("temporary")
        return "ok"

    assert ingest_mod._retry_model_call(transient, sleep=sleeps.append) == "ok"
    assert calls == ["transient", "transient", "transient"]
    assert sleeps

    format_calls = []

    def format_error():
        format_calls.append("format")
        raise ValueError("invalid json")

    with pytest.raises(ValueError):
        ingest_mod._retry_model_call(format_error, sleep=sleeps.append)
    assert format_calls == ["format"]


def test_cluster_failure_does_not_roll_back_processed_article(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "prefilter", lambda title, content="": {"relevant": True, "domain": "AI技术", "channel": "大模型动态"})
    monkeypatch.setattr(ingest_mod, "score", lambda title, content="": {
        "reason": "ok",
        "dims": {"firsthand": 90, "ai_relevance": 90, "power_relevance": 90, "utility": 90, "impact": 90, "depth": 90},
    })
    monkeypatch.setattr(ingest_mod, "enrich", lambda title, content="": {"title_zh": "", "summary": "summary", "tags": [], "org": "AI"})
    monkeypatch.setattr(ingest_mod, "embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(ingest_mod, "assign_cluster", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cluster failed")))

    stats = ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=[_raw("https://stable.example/cluster")]))], run_key="news:cluster")

    article = db.query(schema.Article).one()
    assert stats["inserted"] == 1
    assert stats["curated"] == 1
    assert article.processing_status == "processed"
    assert article.scored is True


def test_articles_bind_to_raw_source_not_aggregator_source(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "process_pending", lambda db, **kw: {"processed": 0, "model_count": 0, "fallback_model_count": 0, "rule_count": 0, "errors": 0})
    raws = [
        RawArticle(title="one", url="https://one.example/a", source_name="One", source_url="https://one.example", source_domain="one.example"),
        RawArticle(title="two", url="https://two.example/a", source_name="Two", source_url="https://two.example", source_domain="two.example"),
    ]

    ingest_once(db, collectors=[ResultCollector(CollectorResult.ok(items=raws))], run_key="news:sources")

    articles = db.query(schema.Article).order_by(schema.Article.title).all()
    assert [article.source.name for article in articles] == ["One", "Two"]
    assert [article.source.url for article in articles] == ["https://one.example", "https://two.example"]


def test_public_rss_requires_adopted_http_source(db, anonymous_client):
    public_source = schema.Source(name="Public", url="https://stable.example/feed", status="已采纳")
    private_source = schema.Source(name="Private", url="builtin://private", status="已采纳")
    pending_source = schema.Source(name="Pending", url="https://pending.example/feed", status="待审核")
    db.add_all([public_source, private_source, pending_source])
    db.flush()
    db.add_all([
        schema.Article(title="public item", url="https://stable.example/public", url_hash="rss-public", summary="ok", curated=True, scored=True, source_id=public_source.id),
        schema.Article(title="no source item", url="https://nosource.example/a", url_hash="rss-nosource", summary="no", curated=True, scored=True),
        schema.Article(title="private item", url="https://private.example/a", url_hash="rss-private", summary="private", curated=True, scored=True, source_id=private_source.id),
        schema.Article(title="pending item", url="https://pending.example/a", url_hash="rss-pending", summary="pending", curated=True, scored=True, source_id=pending_source.id),
    ])
    db.commit()

    rss = anonymous_client.get("/api/rss.xml")

    assert rss.status_code == 200
    assert "public item" in rss.text
    assert "no source item" not in rss.text
    assert "private item" not in rss.text
    assert "pending item" not in rss.text
