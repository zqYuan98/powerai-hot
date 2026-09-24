import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.constants import CHANNELS, KINDS, TIERS
from models import schema
from models import seed
from models.database import Base
from models.migrate import ensure_columns


def test_constants():
    assert CHANNELS == [
        "行业动态", "国网规划", "招标公告", "AI洞察", "政策法规",
        "前沿论文", "大模型动态", "落地案例",
    ]
    assert KINDS == ["资讯", "论文", "案例"]
    assert TIERS == ["T1", "T1.5", "T2"]


def test_article_new_fields_roundtrip(db):
    a = schema.Article(
        title="t", kind="论文", tier="T1", scored=True,
        meta={"arxiv_id": "2507.00001", "authors": ["A", "B"]},
        dim_scores={"firsthand": 90, "relevance": 80, "utility": 70, "impact": 60, "depth": 50},
    )
    db.add(a)
    db.commit()
    got = db.get(schema.Article, a.id)
    assert got.kind == "论文" and got.tier == "T1" and got.scored is True
    assert got.meta["arxiv_id"] == "2507.00001"
    assert got.dim_scores["relevance"] == 80


def test_source_tier_default(db):
    s = schema.Source(name="x", url="http://x")
    db.add(s)
    db.commit()
    assert s.tier == "T2"
    assert s.last_status is None


def test_scoring_config_table(db):
    db.add(schema.ScoringConfig(key="scoring", value={"hot_score": 80}))
    db.commit()
    row = db.get(schema.ScoringConfig, "scoring")
    assert row.value["hot_score"] == 80


def test_ensure_columns_adds_missing(tmp_path):
    """旧库（无新列）经 ensure_columns 后补齐新列。"""
    url = f"sqlite:///{tmp_path/'old.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE articles (id INTEGER PRIMARY KEY, title VARCHAR(400))")
        conn.exec_driver_sql("CREATE TABLE sources (id INTEGER PRIMARY KEY, name VARCHAR(200))")
    ensure_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("articles")}
    assert {"kind", "meta", "dim_scores", "tier", "scored"} <= cols
    scols = {c["name"] for c in inspect(engine).get_columns("sources")}
    assert {"tier", "last_status", "last_error"} <= scols
    # 幂等：重复执行不报错
    ensure_columns(engine)


def test_ensure_columns_backfills_source_keys_and_preserves_first_duplicate(tmp_path):
    url = f"sqlite:///{tmp_path/'sources.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE sources (id INTEGER PRIMARY KEY, name VARCHAR(200), url VARCHAR(500))"
        )
        conn.exec_driver_sql(
            "INSERT INTO sources (id, name, url) VALUES "
            "(1, '  Duplicate  ', 'https://example.com/feed.xml'), "
            "(2, 'Duplicate', 'https://example.com/feed.xml')"
        )

    ensure_columns(engine)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT id, name_key, url_key FROM sources ORDER BY id"
        ).all()
        indexes = {index["name"] for index in inspect(engine).get_indexes("sources")}

    assert rows[0][1:] == ("duplicate", "https://example.com/feed.xml")
    assert rows[1][1].startswith("duplicate#legacy-2")
    assert rows[1][2].startswith("https://example.com/feed.xml#legacy-2")
    assert {"uq_sources_name_key", "uq_sources_url_key"} <= indexes


def test_seed_populates_source_keys_and_is_idempotent(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'seed.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(seed, "SessionLocal", Session)
    monkeypatch.setattr(seed, "init_db", lambda: None)

    seed.run()
    first = Session()
    try:
        source_count = first.query(schema.Source).count()
        sources = first.query(schema.Source).all()
        assert source_count > 0
        assert all(source.name_key and source.url_key for source in sources if source.url)
    finally:
        first.close()

    seed.run()
    second = Session()
    try:
        assert second.query(schema.Source).count() == source_count
        existing = second.query(schema.Source).filter(schema.Source.url != "").first()
        duplicate = schema.Source(
            name=existing.name,
            url="https://seed-duplicate.example.com/feed.xml",
            name_key=schema.normalize_source_name(existing.name),
            url_key=schema.normalize_source_url("https://seed-duplicate.example.com/feed.xml"),
        )
        second.add(duplicate)
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
    finally:
        second.close()


def test_seed_sources_registers_active_power_and_verified_feed_sources(db):
    seed.seed_sources(db)
    db.commit()

    rows = {source.name: source for source in db.query(schema.Source).all()}
    assert {
        "国家能源局",
        "国家电网",
        "南方电网",
        "中国政府采购网",
        "南方电网供应链",
        "OpenAI Blog",
        "MIT Technology Review AI",
        "NVIDIA Blog",
        "IT之家",
    } <= set(rows)
    assert rows["国家能源局"].status == "已采纳"
    assert rows["OpenAI Blog"].submitted_by == "seed"
    assert rows["OpenAI Blog"].type == "RSS"


def test_seed_sources_updates_url_for_seed_managed_feed(db):
    old_url = "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"
    db.add(schema.Source(
        name="Anthropic News",
        url=old_url,
        name_key=schema.normalize_source_name("Anthropic News"),
        url_key=schema.normalize_source_url(old_url),
        type="RSS",
        status="已采纳",
        submitted_by="seed",
    ))
    db.commit()

    seed.seed_sources(db)
    db.commit()

    source = db.query(schema.Source).filter_by(name="Anthropic News").one()
    assert source.url == "https://cdn.jsdelivr.net/gh/Olshansk/rss-feeds@main/feeds/feed_anthropic_news.xml"
