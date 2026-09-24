from datetime import datetime

from sqlalchemy import create_engine, inspect

from analyzer.scoring import DEFAULT_CONFIG
from models import schema
from models.migrate import ensure_columns


def test_default_config_has_cluster_threshold():
    assert DEFAULT_CONFIG["cluster_threshold"] == 0.82


def test_article_cluster_fields_roundtrip(db):
    a = schema.Article(title="t", embedding=[0.1, 0.2], cluster_id="c1", is_cluster_main=False)
    db.add(a)
    db.commit()
    got = db.get(schema.Article, a.id)
    assert got.embedding == [0.1, 0.2]
    assert got.cluster_id == "c1" and got.is_cluster_main is False


def test_article_is_cluster_main_defaults_true(db):
    a = schema.Article(title="t")
    db.add(a)
    db.commit()
    assert a.is_cluster_main is True and a.cluster_id is None


def test_report_roundtrip(db):
    r = schema.Report(type="daily", title="今日精选 · 2026-07-04",
                      content_json={"sections": [], "total": 0},
                      period_start=datetime(2026, 7, 3, 7), period_end=datetime(2026, 7, 4, 7))
    db.add(r)
    db.commit()
    got = db.get(schema.Report, r.id)
    assert got.status == "完成" and got.content_json["total"] == 0


def test_ensure_columns_adds_cluster_fields(tmp_path):
    url = f"sqlite:///{tmp_path/'old.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE articles (id INTEGER PRIMARY KEY, title VARCHAR(400))")
    ensure_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("articles")}
    assert {"embedding", "cluster_id", "is_cluster_main"} <= cols
    ensure_columns(engine)  # 幂等
