from services.clustering import TIER_RANK, assign_cluster, cosine
from models import schema


def test_cosine():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([1, 0], [0, 0]) == 0.0  # 零向量安全


def _art(db, title, tier="T2", score=50, emb=None, **kw):
    a = schema.Article(title=title, tier=tier, relevance_score=score,
                       embedding=emb, scored=True, **kw)
    db.add(a)
    db.commit()
    return a


def test_no_embedding_self_cluster(db):
    a = _art(db, "a", emb=None)
    assign_cluster(db, a, threshold=0.82)
    assert a.cluster_id == f"c{a.id}" and a.is_cluster_main is True


def test_similar_joins_cluster_and_t1_elected_main(db):
    t2 = _art(db, "媒体报道", tier="T2", score=70, emb=[1.0, 0.0])
    assign_cluster(db, t2, threshold=0.82)
    t1 = _art(db, "官方发布", tier="T1", score=65, emb=[0.99, 0.14])  # cos≈0.99
    assign_cluster(db, t1, threshold=0.82)
    db.commit()
    assert t1.cluster_id == t2.cluster_id == f"c{t2.id}"
    assert t1.is_cluster_main is True and t2.is_cluster_main is False  # T1 优先，分低也当主


def test_dissimilar_new_cluster(db):
    a = _art(db, "a", emb=[1.0, 0.0])
    assign_cluster(db, a, threshold=0.82)
    b = _art(db, "b", emb=[0.0, 1.0])
    assign_cluster(db, b, threshold=0.82)
    assert b.cluster_id == f"c{b.id}" and b.is_cluster_main is True


def test_same_tier_higher_score_wins(db):
    lo = _art(db, "低分", tier="T2", score=60, emb=[1.0, 0.0])
    assign_cluster(db, lo, threshold=0.82)
    hi = _art(db, "高分", tier="T2", score=90, emb=[1.0, 0.01])
    assign_cluster(db, hi, threshold=0.82)
    assert hi.is_cluster_main is True and lo.is_cluster_main is False


def test_window_filter_excludes_old(db):
    from datetime import timedelta
    from services.clustering import utcnow
    old = _art(db, "旧闻", emb=[1.0, 0.0])
    old.crawled_at = utcnow() - timedelta(hours=72)  # crawled_at 是 UTC 时钟
    db.commit()
    fresh = _art(db, "新闻", emb=[1.0, 0.0])
    assign_cluster(db, fresh, threshold=0.82, window_hours=48)
    assert fresh.cluster_id == f"c{fresh.id}"  # 72h 前的不参与
