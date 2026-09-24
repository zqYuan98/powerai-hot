"""热点阈值：低热度不返回；上限 5；不足自然减少。"""
from datetime import timedelta

from models import schema
from services.article_feed import HOTSPOT_MIN_HEAT, get_hotspots
from services.clustering import utcnow


def _art(db, title, score, hours_ago=0):
    a = schema.Article(title=title, channel="行业动态", url=f"http://x/{title}",
                       relevance_score=score, curated=True, scored=True, is_cluster_main=True)
    db.add(a)
    db.commit()
    a.crawled_at = utcnow() - timedelta(hours=hours_ago)
    a.published_at = a.crawled_at
    db.commit()
    return a


def test_low_heat_filtered_out(db):
    _art(db, "新鲜高分", 90, hours_ago=1)
    _art(db, "陈旧低分", 40, hours_ago=40)   # heat ≈ 0.4*e^-1.67 ≈ 0.076 < 0.25
    out = get_hotspots(db, limit=5)
    assert [o.title for o in out] == ["新鲜高分"]


def test_cap_at_limit(db):
    for i in range(8):
        _art(db, f"热点{i}", 95, hours_ago=1)
    assert len(get_hotspots(db, limit=5)) == 5


def test_empty_when_nothing_hot(db):
    _art(db, "全都太冷", 30, hours_ago=47)
    assert get_hotspots(db, limit=5) == []
    assert HOTSPOT_MIN_HEAT == 0.25
