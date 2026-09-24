"""入库时间线：逐小时分桶、空桶连续、精选计数、窗口过滤。"""
from datetime import timedelta

from models import schema
from services.article_feed import get_timeline
from services.clustering import utcnow


def _art(db, title, hours_ago, curated=False):
    a = schema.Article(title=title, channel="行业动态", url=f"http://x/{title}",
                       curated=curated, scored=True, is_cluster_main=True)
    db.add(a)
    db.commit()
    a.crawled_at = utcnow() - timedelta(hours=hours_ago)
    db.commit()
    return a


def test_timeline_buckets_by_hour(db):
    _art(db, "一小时前A", 1)
    _art(db, "一小时前B", 1, curated=True)
    _art(db, "五小时前", 5)
    _art(db, "窗口外", 80)

    out = get_timeline(db, hours=48)
    assert len(out["buckets"]) in (48, 49)  # 跨整点边界时可能多一桶
    assert out["latest_crawled_at"] is not None

    non_empty = [b for b in out["buckets"] if b["count"] > 0]
    total = sum(b["count"] for b in non_empty)
    assert total == 3  # 窗口外的不计
    by_count = sorted(non_empty, key=lambda b: b["count"], reverse=True)
    assert by_count[0]["count"] == 2 and by_count[0]["curated"] == 1

    # 桶按时间升序且逐小时连续
    ts = [b["ts"] for b in out["buckets"]]
    assert all((b - a) == timedelta(hours=1) for a, b in zip(ts, ts[1:]))


def test_timeline_api(client, db):
    _art(db, "刚入库", 0, curated=True)
    resp = client.get("/api/articles/timeline?hours=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_crawled_at"]
    assert sum(b["count"] for b in data["buckets"]) == 1
    assert sum(b["curated"] for b in data["buckets"]) == 1
    # hours 参数夹取
    assert client.get("/api/articles/timeline?hours=1").status_code == 422
    assert client.get("/api/articles/timeline?hours=999").status_code == 422


def test_timeline_empty_db(client):
    resp = client.get("/api/articles/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_crawled_at"] is None
    assert all(b["count"] == 0 for b in data["buckets"])
