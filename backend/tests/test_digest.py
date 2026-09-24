from datetime import timedelta

from models import schema
from services.clustering import utcnow
from services.digest import SECTIONS, build_daily_digest


def _art(db, title, channel, score, *, curated=True, main=True, hours_ago=1):
    a = schema.Article(title=title, channel=channel, relevance_score=score,
                       curated=curated, is_cluster_main=main, scored=True)
    db.add(a)
    db.commit()
    a.crawled_at = utcnow() - timedelta(hours=hours_ago)  # crawled_at 是 UTC 时钟
    db.commit()
    return a


def test_sections_cover_all_channels():
    covered = [ch for _, chs in SECTIONS for ch in chs]
    from core.constants import CHANNELS
    assert sorted(covered) == sorted(CHANNELS)  # 8 频道全覆盖不丢内容


def test_bucketing_sorting_and_filters(db):
    p1 = _art(db, "论文高分", "前沿论文", 90)
    p2 = _art(db, "论文低分", "前沿论文", 70)
    _art(db, "非精选", "前沿论文", 90, curated=False)      # 不进日报
    _art(db, "折叠条", "前沿论文", 95, main=False)          # 非主条不进
    _art(db, "过期", "前沿论文", 95, hours_ago=30)          # 超24h不进
    n = _art(db, "国网新闻", "行业动态", 80)

    r = build_daily_digest(db)
    sec = {s["name"]: s["article_ids"] for s in r.content_json["sections"]}
    assert sec["论文研究"] == [p1.id, p2.id]  # 按分排序
    assert sec["行业·国网动态"] == [n.id]
    assert r.content_json["total"] == 3
    assert r.type == "daily" and r.status == "完成"


def test_idempotent_same_day_updates(db):
    _art(db, "a", "前沿论文", 90)
    r1 = build_daily_digest(db)
    _art(db, "b", "前沿论文", 95)
    r2 = build_daily_digest(db)
    assert r1.id == r2.id  # 同日重复生成是更新不是新建
    assert db.query(schema.Report).count() == 1
    assert r2.content_json["total"] == 2
