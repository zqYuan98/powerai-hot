"""采集一个信源：抓取 → upsert（first/last_seen）→ 记录 source_run → 返回新增条目 id。"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CollectorResult, RawItem
from app.collectors.http import PoliteClient
from app.collectors.registry import build_collector
from app.collectors.textutil import canonical_url, clean_text
from app.core.htmlsanitize import sanitize_html
from app.models import Item, Source, SourceRun
from app.pipeline.knowledge import upsert_articles

# 发布时间早于此的条目直接丢弃（历史存量不值得花模型钱）
MAX_AGE_DAYS = 30


@dataclass
class CollectOutcome:
    source_key: str
    fetched: int
    new_ids: list[int]
    healthy: bool
    error: str | None
    knowledge: bool = False  # 为真时 new_ids 是知识库文章 id


def is_knowledge_source(source: Source) -> bool:
    return (source.config or {}).get("target") == "knowledge"


def _row(source: Source, raw: RawItem, now: datetime) -> dict[str, object]:
    url = raw.url.strip()
    return {
        "source_id": source.id,
        "tier": source.tier,
        "url": url,
        "url_hash": hashlib.sha256(canonical_url(url).encode()).hexdigest(),
        "external_id": raw.external_id,
        "title": clean_text(raw.title)[:500],
        "content_text": raw.content_text,
        "content_html": (sanitize_html(raw.content_html) or None) if raw.content_html else None,
        "published_at": raw.published_at,
        "first_seen_at": now,
        "last_seen_at": now,
        "channel": raw.channel_hint or source.category,
    }


async def upsert_items(session: AsyncSession, source: Source, raws: list[RawItem]) -> list[int]:
    now = datetime.now(UTC)
    fresh = [r for r in raws if r.published_at is None or (now - r.published_at).days <= MAX_AGE_DAYS]
    if not fresh:
        return []
    rows = list({row["url_hash"]: row for row in (_row(source, r, now) for r in fresh)}.values())
    # 已存在：只刷新 last_seen_at；PostgreSQL 的 xmax = 0 区分「新插入」与「冲突更新」
    upsert = insert(Item).values(rows).on_conflict_do_update(
        index_elements=[Item.url_hash], set_={"last_seen_at": now}
    )
    result: Any = await session.execute(upsert.returning(Item.id, literal_column("(xmax = 0)").label("inserted")))
    return [r.id for r in result if r.inserted]


async def collect_source(session: AsyncSession, client: PoliteClient, source: Source) -> CollectOutcome:
    started = time.monotonic()
    try:
        collector = build_collector(source.key, source.kind, source.url, source.config)
        result = await collector.fetch(client)
    except Exception as exc:  # 采集器自身 bug 也要落到健康记录里
        result = CollectorResult.fail("network_error", f"{type(exc).__name__}: {exc}", parse="parse_error")

    knowledge = is_knowledge_source(source)
    upsert = upsert_articles if knowledge else upsert_items
    new_ids = await upsert(session, source, result.items) if result.items else []
    now = datetime.now(UTC)
    session.add(SourceRun(
        source_id=source.id,
        started_at=now,
        duration_ms=int((time.monotonic() - started) * 1000),
        transport_status=result.transport_status,
        parse_status=result.parse_status,
        http_status=result.http_status,
        fetched=len(result.items),
        new_count=len(new_ids),
        error=result.error,
    ))
    source.last_run_at = now
    if result.healthy:
        source.last_ok_at = now
        source.fail_streak = 0
        source.last_error = result.error  # partial 时保留提示
    else:
        source.fail_streak += 1
        source.last_error = result.error
    await session.commit()
    return CollectOutcome(source.key, len(result.items), new_ids, result.healthy, result.error, knowledge)


async def due_sources(session: AsyncSession, now: datetime | None = None) -> list[Source]:
    """到期的启用信源。连续失败的信源退避（最多 8 倍间隔），避免反复敲打挂掉的站点。"""
    now = now or datetime.now(UTC)
    sources = (await session.scalars(select(Source).where(Source.enabled))).all()
    due = []
    for s in sources:
        backoff = min(2 ** min(s.fail_streak, 3), 8)
        if s.last_run_at is None or (now - s.last_run_at).total_seconds() >= s.interval_min * 60 * backoff:
            due.append(s)
    return due
