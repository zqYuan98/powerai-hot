from __future__ import annotations

import hashlib
import json
import sqlite3

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from jobs.migrate_sqlite import migrate_sqlite_to_database
from models.database import Base
from models import schema


def _make_sqlite(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return engine, Session


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_legacy_sqlite(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sources (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            url VARCHAR(500) NOT NULL,
            name_key VARCHAR(400),
            url_key VARCHAR(1000),
            type VARCHAR(20),
            status VARCHAR(20),
            submitted_by VARCHAR(100),
            reason TEXT,
            tier VARCHAR(8),
            last_status VARCHAR(16),
            last_error TEXT,
            crawl_interval_hours INTEGER,
            last_crawled_at DATETIME,
            created_at DATETIME
        );
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            title VARCHAR(400) NOT NULL,
            content TEXT,
            content_html TEXT,
            summary TEXT,
            tags JSON,
            channel VARCHAR(40),
            org VARCHAR(80),
            hot BOOLEAN,
            deadline_days INTEGER,
            source_id INTEGER,
            source_domain VARCHAR(120),
            url VARCHAR(600),
            url_hash VARCHAR(64),
            published_at DATETIME,
            published_label VARCHAR(40),
            crawled_at DATETIME,
            view_count INTEGER,
            relevance_score INTEGER,
            recommend_reason TEXT,
            curated BOOLEAN,
            kind VARCHAR(8),
            meta JSON,
            dim_scores JSON,
            tier VARCHAR(8),
            scored BOOLEAN,
            noise_reason VARCHAR(200),
            embedding JSON,
            cluster_id VARCHAR(24),
            is_cluster_main BOOLEAN
        );
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY,
            user_id VARCHAR(100),
            keywords JSON,
            notify_in_app BOOLEAN,
            notify_bid_deadline BOOLEAN,
            notify_email_digest BOOLEAN
        );
        CREATE TABLE scoring_config (
            key VARCHAR(40) PRIMARY KEY,
            value JSON
        );
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY,
            type VARCHAR(16),
            title VARCHAR(200),
            content_md TEXT,
            content_json JSON,
            topic VARCHAR(200),
            period_start DATETIME,
            period_end DATETIME,
            status VARCHAR(8),
            created_at DATETIME
        );
        CREATE TABLE favorites (
            id INTEGER PRIMARY KEY,
            article_id INTEGER,
            created_at DATETIME
        );
        CREATE TABLE knowledge_cards (
            id INTEGER PRIMARY KEY,
            article_id INTEGER,
            category VARCHAR(16),
            problem TEXT,
            method TEXT,
            conclusion TEXT,
            power_relevance TEXT,
            note TEXT,
            status VARCHAR(8),
            created_at DATETIME,
            updated_at DATETIME
        );
        """
    )
    conn.execute(
        "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            33,
            "AIHOT",
            "https://aihot.example/feed",
            "aihot",
            "https://aihot.example/feed",
            "RSS",
            "已采纳",
            None,
            None,
            "T1",
            "ok",
            None,
            1,
            "2026-07-17 00:00:00",
            "2026-07-16 00:00:00",
        ),
    )
    article_rows = [
        (
            1152,
            "legacy article",
            "raw",
            "<p>raw</p>",
            "summary",
            json.dumps(["grid", "ai"]),
            "行业动态",
            "国家电网",
            1,
            None,
            33,
            "aihot.example",
            "https://aihot.example/a",
            "hash-a",
            "2026-07-17 01:02:03",
            "1 小时前",
            "2026-07-17 02:00:00",
            7,
            88,
            "good",
            1,
            "资讯",
            json.dumps({"model": "legacy"}),
            json.dumps({"impact": 90}),
            "T1",
            1,
            None,
            json.dumps([0.1, 0.2]),
            "cluster-a",
            1,
        ),
        (
            1153,
            "backfill source only by domain",
            None,
            None,
            None,
            json.dumps([]),
            "行业动态",
            None,
            0,
            None,
            None,
            "aihot.example",
            "https://aihot.example/b",
            "hash-b",
            None,
            None,
            "2026-07-17 03:00:00",
            0,
            0,
            None,
            0,
            "资讯",
            None,
            None,
            "T2",
            0,
            None,
            None,
            None,
            1,
        ),
    ]
    conn.executemany(
        "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        article_rows,
    )
    conn.execute(
        "INSERT INTO subscriptions VALUES (?,?,?,?,?,?)",
        (1, "me", json.dumps(["调度"]), 1, 0, 1),
    )
    conn.execute("INSERT INTO scoring_config VALUES (?,?)", ("default", json.dumps({"weights": {"impact": 1}})))
    conn.execute(
        "INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            1,
            "daily",
            "report",
            "# report",
            json.dumps({"sections": []}),
            None,
            "2026-07-17 00:00:00",
            "2026-07-18 00:00:00",
            "完成",
            "2026-07-17 06:00:00",
        ),
    )
    conn.execute("INSERT INTO favorites VALUES (?,?,?)", (1, 1152, "2026-07-17 07:00:00"))
    conn.execute(
        "INSERT INTO knowledge_cards VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, 1152, "大模型", "p", "m", "c", "r", "n", "完成", "2026-07-17 08:00:00", "2026-07-17 08:00:00"),
    )
    conn.commit()
    conn.close()


def test_sqlite_migration_is_idempotent_and_preserves_relationships(tmp_path):
    src_engine, Src = _make_sqlite(tmp_path / "source.db")
    src = Src()
    source = schema.Source(id=33, name="AIHOT", url="https://aihot.example", status="已采纳")
    article = schema.Article(
        id=1152,
        title="迁移文章",
        url="https://aihot.example/a",
        url_hash="hash-a",
        source=source,
        published_at=None,
    )
    src.add_all([source, article, schema.Favorite(id=1, article_id=1152)])
    src.commit()
    src.close()

    dst_engine, Dst = _make_sqlite(tmp_path / "target.db")
    first = migrate_sqlite_to_database(str(tmp_path / "source.db"), dst_engine)
    second = migrate_sqlite_to_database(str(tmp_path / "source.db"), dst_engine)

    assert first["tables"]["articles"]["inserted"] == 1
    assert second["tables"]["articles"]["skipped"] == 1
    dst = Dst()
    migrated = dst.scalar(select(schema.Article).where(schema.Article.id == 1152))
    assert migrated is not None
    assert migrated.source_id == 33
    assert dst.query(schema.Favorite).filter_by(article_id=1152).count() == 1
    assert first["post_counts"]["articles"] == 1
    dst.close()


def test_legacy_sqlite_schema_migrates_readonly_with_type_and_relation_gate(tmp_path):
    source_path = tmp_path / "legacy.db"
    _make_legacy_sqlite(source_path)
    before_hash = _file_hash(source_path)
    before_mtime = source_path.stat().st_mtime_ns

    dst_engine, Dst = _make_sqlite(tmp_path / "target.db")
    summary = migrate_sqlite_to_database(str(source_path), dst_engine)
    second = migrate_sqlite_to_database(str(source_path), dst_engine)

    assert _file_hash(source_path) == before_hash
    assert source_path.stat().st_mtime_ns == before_mtime
    assert set(summary["tables"]) == {
        "sources",
        "articles",
        "subscriptions",
        "scoring_config",
        "reports",
        "favorites",
        "knowledge_cards",
    }
    assert summary["tables"]["articles"]["read"] == 2
    assert summary["tables"]["articles"]["inserted"] == 2
    assert second["tables"]["articles"]["skipped"] == 2
    assert summary["gate_passed"] is True
    assert summary["relationship_checks"] == {
        "orphan_articles": 0,
        "orphan_favorites": 0,
        "orphan_knowledge_cards": 0,
    }
    assert summary["backfill"]["articles_source_id_by_domain"] == 1
    assert summary["backfill"]["articles_source_id_ambiguous"] == 0

    db = Dst()
    migrated = db.scalar(select(schema.Article).where(schema.Article.id == 1152))
    backfilled = db.scalar(select(schema.Article).where(schema.Article.id == 1153))
    config = db.scalar(select(schema.ScoringConfig).where(schema.ScoringConfig.key == "default"))
    subscription = db.scalar(select(schema.Subscription).where(schema.Subscription.id == 1))
    assert migrated.tags == ["grid", "ai"]
    assert migrated.meta == {"model": "legacy"}
    assert migrated.dim_scores == {"impact": 90}
    assert migrated.embedding == [0.1, 0.2]
    assert migrated.hot is True
    assert migrated.curated is True
    assert migrated.scored is True
    assert migrated.published_at.isoformat() == "2026-07-17T01:02:03"
    assert backfilled.source_id == 33
    assert backfilled.published_at is None
    assert config.value == {"weights": {"impact": 1}}
    assert subscription.keywords == ["调度"]
    db.close()


def test_timezone_aware_legacy_datetimes_normalize_to_utc_naive_and_remain_idempotent(tmp_path):
    source_path = tmp_path / "legacy.db"
    _make_legacy_sqlite(source_path)
    conn = sqlite3.connect(source_path)
    conn.execute(
        "UPDATE articles SET published_at = ?, crawled_at = ? WHERE id = ?",
        ("2026-07-17T09:02:03+08:00", "2026-07-17T01:02:03Z", 1152),
    )
    conn.commit()
    conn.close()

    dst_engine, Dst = _make_sqlite(tmp_path / "target.db")
    first = migrate_sqlite_to_database(str(source_path), dst_engine)
    second = migrate_sqlite_to_database(str(source_path), dst_engine)

    assert first["tables"]["articles"]["inserted"] == 2
    assert second["tables"]["articles"]["skipped"] == 2
    assert second["tables"]["articles"]["conflicts"] == 0
    assert second["gate_passed"] is True

    db = Dst()
    migrated = db.scalar(select(schema.Article).where(schema.Article.id == 1152))
    assert migrated.published_at.isoformat() == "2026-07-17T01:02:03"
    assert migrated.crawled_at.isoformat() == "2026-07-17T01:02:03"
    assert migrated.published_at.tzinfo is None
    assert migrated.crawled_at.tzinfo is None
    db.close()


def test_sqlite_migration_reports_conflicts_as_gate_failure(tmp_path):
    source_path = tmp_path / "legacy.db"
    _make_legacy_sqlite(source_path)
    dst_engine, _ = _make_sqlite(tmp_path / "target.db")

    migrate_sqlite_to_database(str(source_path), dst_engine)
    conn = sqlite3.connect(source_path)
    conn.execute("UPDATE articles SET title = ? WHERE id = ?", ("changed title", 1152))
    conn.commit()
    conn.close()

    summary = migrate_sqlite_to_database(str(source_path), dst_engine)

    assert summary["tables"]["articles"]["conflicts"] == 1
    assert summary["gate_passed"] is False
    assert "articles" in summary["blocking_failures"]["conflict_tables"]


def test_sqlite_migration_rolls_back_new_rows_when_gate_fails_after_conflict(tmp_path):
    source_path = tmp_path / "legacy.db"
    target_path = tmp_path / "target.db"
    _make_legacy_sqlite(source_path)
    dst_engine, Dst = _make_sqlite(target_path)

    first = migrate_sqlite_to_database(str(source_path), dst_engine)
    assert first["gate_passed"] is True

    divergent_title = "target divergent article"
    conn = sqlite3.connect(target_path)
    conn.execute("UPDATE articles SET title = ? WHERE id = ?", (divergent_title, 1152))
    conn.execute("DELETE FROM articles WHERE id = ?", (1153,))
    conn.commit()
    conn.close()

    summary = migrate_sqlite_to_database(str(source_path), dst_engine)

    assert summary["tables"]["articles"]["conflicts"] == 1
    assert summary["tables"]["articles"]["inserted"] == 1
    assert summary["gate_passed"] is False
    assert "articles" in summary["blocking_failures"]["conflict_tables"]

    db = Dst()
    conflicted = db.scalar(select(schema.Article).where(schema.Article.id == 1152))
    inserted_after_gate_failure = db.scalar(select(schema.Article).where(schema.Article.id == 1153))
    assert conflicted.title == divergent_title
    assert inserted_after_gate_failure is None
    db.close()
