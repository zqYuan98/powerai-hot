"""Bounded article-feed queries with stable seek cursors."""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from api.dto import ArticleOut
from core.sqlutil import escape_like
from models import schema

FeedView = Literal["curated", "all", "noise"]
FeedWindow = Literal["24h", "7d", "all"]
FeedSort = Literal["score", "latest"]


@dataclass(frozen=True)
class FeedQuery:
    channel: str | None = None
    thread_id: int | None = None
    q: str | None = None
    kind: str | None = None
    min_score: int = 0
    view: FeedView = "curated"
    window: FeedWindow = "all"
    tag: str | None = None
    sort: FeedSort = "score"
    include_all: bool = False
    axis: str | None = None  # 交叉 | AI | 行业 | 弱

    def normalized(self) -> "FeedQuery":
        return FeedQuery(
            channel=(self.channel or "").strip() or None,
            thread_id=self.thread_id,
            q=(self.q or "").strip() or None,
            kind=(self.kind or "").strip() or None,
            min_score=self.min_score,
            view=self.view,
            window=self.window,
            tag=(self.tag or "").strip() or None,
            sort=self.sort,
            include_all=self.include_all,
            axis=(self.axis or "").strip() or None,
        )

    def fingerprint(self) -> str:
        raw = json.dumps(asdict(self.normalized()), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _b64encode(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> dict:
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw)
    except Exception as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid cursor")
    return payload


def _to_epoch_us(value: datetime) -> int:
    utc_value = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return int(utc_value.timestamp() * 1_000_000)


def _from_epoch_us(value: object) -> datetime:
    if type(value) is not int:
        raise ValueError("invalid cursor")
    try:
        return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("invalid cursor") from exc


def encode_cursor(query: FeedQuery, article: schema.Article) -> str:
    if article.crawled_at is None:
        raise ValueError("article crawled_at is required for pagination")
    payload = {"v": 1, "sort": query.sort, "fp": query.fingerprint(),
               "t": _to_epoch_us(article.crawled_at), "id": article.id}
    if query.sort == "score":
        payload["score"] = article.relevance_score or 0
    return _b64encode(payload)


def decode_cursor(value: str, query: FeedQuery) -> dict:
    payload = _b64decode(value)
    if payload.get("v") != 1 or payload.get("sort") != query.sort or payload.get("fp") != query.fingerprint():
        raise ValueError("cursor does not match query")
    if type(payload.get("id")) is not int or payload["id"] <= 0:
        raise ValueError("invalid cursor")
    payload["crawled_at"] = _from_epoch_us(payload.get("t"))
    if query.sort == "score" and type(payload.get("score")) is not int:
        raise ValueError("invalid cursor")
    return payload


def build_filters(query: FeedQuery, dialect_name: str = "sqlite") -> list:
    query = query.normalized()
    filters = []
    if query.channel:
        filters.append(schema.Article.channel == query.channel)
    if query.thread_id is not None:
        filters.append(schema.Article.primary_thread_id == query.thread_id)
    if query.kind:
        filters.append(schema.Article.kind == query.kind)
    if not query.include_all:
        filters.append(schema.Article.is_cluster_main.isnot(False))
    if query.view == "curated":
        filters.extend((
            schema.Article.curated.is_(True),
            schema.Article.scored.is_(True),
            schema.Article.noise_reason.is_(None),
        ))
    elif query.view == "all":
        filters.extend((
            schema.Article.scored.is_(True),
            schema.Article.noise_reason.is_(None),
        ))
    else:
        filters.append(or_(
            schema.Article.noise_reason.isnot(None),
            schema.Article.scored.is_(False),
        ))
    if query.min_score > 0:
        filters.append(func.coalesce(schema.Article.relevance_score, 0) >= query.min_score)
    if query.q:
        like = f"%{escape_like(query.q)}%"
        filters.append(or_(schema.Article.title.ilike(like, escape="\\"),
                           schema.Article.summary.ilike(like, escape="\\")))
    if query.window != "all":
        hours = 24 if query.window == "24h" else 7 * 24
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        filters.append(or_(
            schema.Article.published_at >= cutoff,
            and_(schema.Article.published_at.is_(None), schema.Article.crawled_at >= cutoff),
        ))
    if query.tag:
        if dialect_name == "postgresql":
            filters.append(schema.Article.tags.any(query.tag))
        else:
            tag_rows = func.json_each(schema.Article.tags).table_valued("key", "value").alias("article_tags")
            filters.append(exists(select(1).select_from(tag_rows).where(tag_rows.c.value == query.tag)))
    if query.axis:
        filters.append(schema.Article.axis == query.axis)
    return filters


def fetch_page(db: Session, query: FeedQuery, *, limit: int, cursor: str | None) -> dict:
    query = query.normalized()
    dialect_name = db.get_bind().dialect.name
    filters = build_filters(query, dialect_name)
    total = int(db.scalar(select(func.count()).select_from(schema.Article).where(*filters)) or 0)
    stmt = select(schema.Article).where(*filters)
    if cursor:
        decoded = decode_cursor(cursor, query)
        if query.sort == "score":
            score = func.coalesce(schema.Article.relevance_score, 0)
            stmt = stmt.where(or_(
                score < decoded["score"],
                and_(score == decoded["score"], schema.Article.crawled_at < decoded["crawled_at"]),
                and_(score == decoded["score"], schema.Article.crawled_at == decoded["crawled_at"], schema.Article.id < decoded["id"]),
            ))
        else:
            stmt = stmt.where(or_(schema.Article.crawled_at < decoded["crawled_at"],
                                  and_(schema.Article.crawled_at == decoded["crawled_at"], schema.Article.id < decoded["id"])))
    if query.sort == "score":
        stmt = stmt.order_by(func.coalesce(schema.Article.relevance_score, 0).desc(),
                             schema.Article.crawled_at.desc(), schema.Article.id.desc())
    else:
        stmt = stmt.order_by(schema.Article.crawled_at.desc(), schema.Article.id.desc())
    rows = list(db.scalars(stmt.limit(limit + 1)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    hashes = {row.cluster_id for row in rows if row.cluster_id}
    counts = dict(db.execute(select(schema.Article.cluster_id, func.count())
                             .where(schema.Article.cluster_id.in_(hashes))
                             .group_by(schema.Article.cluster_id)).all()) if hashes else {}
    items = []
    for row in rows:
        dto = ArticleOut.model_validate(row)
        dto.related_count = max(0, counts.get(row.cluster_id or "", 1) - 1)
        items.append(dto)
    return {"items": items,
            "next_cursor": encode_cursor(query, rows[-1]) if has_more and rows else None,
            "has_more": has_more, "total": total}


def count_channels(db: Session, query: FeedQuery) -> dict[str, int]:
    query = query.normalized()
    query = FeedQuery(**{**asdict(query), "channel": None})
    filters = build_filters(query, db.get_bind().dialect.name)
    return dict(db.execute(
        select(schema.Article.channel, func.count())
        .where(*filters)
        .group_by(schema.Article.channel)
    ).all())


def get_freshness(db: Session) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    latest = db.scalar(select(func.max(schema.Article.crawled_at)))
    added = int(db.scalar(select(func.count()).select_from(schema.Article)
                          .where(schema.Article.crawled_at >= cutoff)) or 0)
    curated = int(db.scalar(select(func.count()).select_from(schema.Article).where(
        schema.Article.crawled_at >= cutoff,
        schema.Article.curated.is_(True),
        schema.Article.scored.is_(True),
        schema.Article.noise_reason.is_(None),
        schema.Article.is_cluster_main.isnot(False),
    )) or 0)
    return {"latest_crawled_at": latest, "added_24h": added, "curated_24h": curated}


def get_timeline(db: Session, hours: int = 48) -> dict:
    """入库时间线：近 N 小时逐小时入库量（含空桶，空桶即「这一小时没采到东西」）。

    分桶在 Python 侧做（窗口内行数有限），避免 SQLite/PG 的日期函数方言差异。
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = (now - timedelta(hours=hours - 1)).replace(minute=0, second=0, microsecond=0)
    rows = db.execute(
        select(schema.Article.crawled_at, schema.Article.curated, schema.Article.noise_reason)
        .where(schema.Article.crawled_at >= start)
    ).all()
    counted: dict[datetime, list[int]] = {}
    for crawled_at, curated, noise_reason in rows:
        if crawled_at is None:
            continue
        key = crawled_at.replace(minute=0, second=0, microsecond=0)
        bucket = counted.setdefault(key, [0, 0])
        bucket[0] += 1
        if curated and noise_reason is None:
            bucket[1] += 1
    buckets = []
    cursor = start
    while cursor <= now:
        count, curated_n = counted.get(cursor, [0, 0])
        buckets.append({"ts": cursor, "count": count, "curated": curated_n})
        cursor += timedelta(hours=1)
    latest = db.scalar(select(func.max(schema.Article.crawled_at)))
    return {"latest_crawled_at": latest, "buckets": buckets}


# 热点最低热度阈值：低于此值不作为「当前热点」展示，实现「随热度自然退场」。
# 热度 = (1+相关报道数) × 分数/100 × exp(-小时/24)。校准（阈值 0.25）：
# 新鲜条目（<几小时）分数 ≥25 可入；约 24h 前的单源条目需 ≥68 分；
# 约 48h 前需多源聚合或 90+ 高分才留得住。
HOTSPOT_MIN_HEAT = 0.25


def get_hotspots(db: Session, limit: int) -> list[ArticleOut]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=48)
    rows = list(db.scalars(select(schema.Article).where(
        schema.Article.curated.is_(True),
        schema.Article.scored.is_(True),
        schema.Article.noise_reason.is_(None),
        schema.Article.is_cluster_main.isnot(False),
        or_(schema.Article.published_at >= cutoff,
            and_(schema.Article.published_at.is_(None), schema.Article.crawled_at >= cutoff)),
    )).all())
    hashes = {row.cluster_id for row in rows if row.cluster_id}
    counts = dict(db.execute(select(schema.Article.cluster_id, func.count())
                             .where(schema.Article.cluster_id.in_(hashes))
                             .group_by(schema.Article.cluster_id)).all()) if hashes else {}

    def heat(row: schema.Article) -> float:
        event_time = row.published_at or row.crawled_at or now
        age_hours = max(0.0, (now - event_time).total_seconds() / 3600)
        related = max(0, counts.get(row.cluster_id or "", 1) - 1)
        return (1 + related) * ((row.relevance_score or 0) / 100) * (2.718281828 ** (-age_hours / 24))

    ranked = [row for row in sorted(rows, key=heat, reverse=True) if heat(row) >= HOTSPOT_MIN_HEAT]
    out = []
    for row in ranked[:limit]:
        dto = ArticleOut.model_validate(row)
        dto.related_count = max(0, counts.get(row.cluster_id or "", 1) - 1)
        out.append(dto)
    return out


def get_cross_picks(db: Session, limit: int) -> list[ArticleOut]:
    """交叉精选：两轴都命中的情报，本产品的核心价值所在。

    与 get_hotspots 的区别：热点按「热度 = 相关分 × 多源报道 × 时间衰减」排，
    衡量的是「大家都在说什么」；交叉精选按 cross_score 排，衡量的是
    「AI 技术与电力业务的交集有多深」——后者才是这个产品区别于普通 AI 资讯站的东西。
    实测交叉区仅占非噪音条目的 4%（19/474），埋在筛选器后面基本不会被看到，
    因此单独提到首屏。
    """
    rows = list(db.scalars(
        select(schema.Article)
        .where(
            schema.Article.axis == "交叉",
            schema.Article.curated.is_(True),
            schema.Article.scored.is_(True),
            schema.Article.is_cluster_main.isnot(False),
            schema.Article.noise_reason.is_(None),
        )
        .order_by(schema.Article.cross_score.desc(), schema.Article.crawled_at.desc())
        .limit(limit)
    ).all())
    return [ArticleOut.model_validate(row) for row in rows]
