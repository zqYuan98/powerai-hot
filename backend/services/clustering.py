"""事件聚类（纯代码）：近窗口余弦相似归簇，官方源优先当主条。

主条规则：tier 高者优先（T1 > T1.5 > T2），同 tier 比质量分，再比先入库。
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import schema

TIER_RANK = {"T1": 0, "T1.5": 1, "T2": 2}


def utcnow() -> datetime:
    """crawled_at 由 server_default 写入（SQLite 存 UTC），窗口比较必须用同一时钟，
    否则本地 UTC+8 下窗口会缩水 8 小时。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def assign_cluster(db: Session, article: schema.Article, *, threshold: float,
                   window_hours: int = 48) -> None:
    """为文章归簇并重选簇内主条。embedding 为空则自成一簇。需已入库（有 id）。"""
    if not article.embedding:
        article.cluster_id = article.cluster_id or f"c{article.id}"
        article.is_cluster_main = True
        return

    since = utcnow() - timedelta(hours=window_hours)
    candidates = db.scalars(
        select(schema.Article).where(
            schema.Article.id != article.id,
            schema.Article.embedding.isnot(None),
            schema.Article.crawled_at >= since,
        )
    ).all()

    best, best_sim = None, 0.0
    for c in candidates:
        if not c.embedding:
            continue  # 防御 JSON 'null'（显式存过 None 的旧行会通过 IS NOT NULL 过滤）
        sim = cosine(article.embedding, c.embedding)
        if sim > best_sim:
            best, best_sim = c, sim

    if best is not None and best_sim >= threshold and best.cluster_id:
        article.cluster_id = best.cluster_id
    else:
        article.cluster_id = f"c{article.id}"
    _elect_main(db, article.cluster_id)


def _elect_main(db: Session, cluster_id: str) -> None:
    # 生产 SessionLocal 是 autoflush=False：先把 pending 的 cluster_id 刷进库，
    # 否则下面的 SELECT 看不到刚归簇的文章，会选出两个主条。
    db.flush()
    members = db.scalars(
        select(schema.Article).where(schema.Article.cluster_id == cluster_id)
    ).all()
    if not members:
        return
    main = min(members, key=lambda a: (TIER_RANK.get(a.tier, 2), -(a.relevance_score or 0), a.id))
    for m in members:
        m.is_cluster_main = (m.id == main.id)
