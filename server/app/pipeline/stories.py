"""事件/项目归并、主稿选举与热度。

归并顺序（先硬后软）：招标编号 → 规范化项目名 → 模型 event_key → 向量近邻（7 天）→ 标题二字组 Jaccard（3 天）。
归并在全局 advisory lock 下串行执行，避免并发处理同一事件时各建一个 story。
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, Story

STORY_LOCK_ID = 7_420_001
VECTOR_WINDOW = timedelta(days=7)
JACCARD_WINDOW = timedelta(days=3)
JACCARD_THRESHOLD = 0.6
HEAT_HALF_LIFE_H = 24.0
TIER_RANK = {"T1": 0, "T1_5": 1, "T2": 2}

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)
_BOILERPLATE = re.compile(r"(招标公告|采购公告|公开招标|中标候选人公示|中标结果公告|成交公告|结果公示|公告|招标|采购)$")


def normalize_key(text: str) -> str:
    return _PUNCT.sub("", text).lower()[:150]


def bigrams(title: str) -> set[str]:
    core = _BOILERPLATE.sub("", _PUNCT.sub("", title.lower()))
    return {core[i:i + 2] for i in range(len(core) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def story_keys(item: Item) -> list[str]:
    keys: list[str] = []
    if item.lead and item.lead.bid_no:
        keys.append("bid:" + normalize_key(item.lead.bid_no))
    if item.lead and item.lead.project_name and len(item.lead.project_name) >= 8:
        keys.append("proj:" + normalize_key(item.lead.project_name))
    if item.event_key:
        keys.append("evt:" + item.event_key[:150])
    return keys


async def _find_similar_story(session: AsyncSession, item: Item, similarity: float) -> int | None:
    now = datetime.now(UTC)
    if item.embedding is not None:
        distance = Item.embedding.cosine_distance(item.embedding)
        row = (await session.execute(
            select(Item.story_id, distance.label("d"))
            .where(Item.id != item.id, Item.story_id.is_not(None), Item.embedding.is_not(None),
                   Item.first_seen_at >= now - VECTOR_WINDOW)
            .order_by(distance)
            .limit(1)
        )).first()
        if row is not None and row.d <= 1 - similarity:
            return int(row.story_id)
    grams = bigrams(item.title_zh or item.title)
    if len(grams) < 4:
        return None
    rows = (await session.execute(
        select(Item.story_id, Item.title, Item.title_zh)
        .where(Item.id != item.id, Item.story_id.is_not(None), Item.status == "analyzed",
               Item.first_seen_at >= now - JACCARD_WINDOW)
        .order_by(Item.id.desc())
        .limit(400)
    )).all()
    best = max(rows, key=lambda r: jaccard(grams, bigrams(r.title_zh or r.title)), default=None)
    if best is not None and jaccard(grams, bigrams(best.title_zh or best.title)) >= JACCARD_THRESHOLD:
        return int(best.story_id)
    return None


async def assign_story(session: AsyncSession, item: Item, *, similarity: float) -> Story:
    """给条目挂上 story（必要时新建），刷新统计并重新选举主稿。调用方负责提交。"""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": STORY_LOCK_ID})
    keys = story_keys(item)
    story: Story | None = None
    if keys:
        story = (await session.scalars(select(Story).where(Story.key.in_(keys)).limit(1))).first()
    if story is None and (story_id := await _find_similar_story(session, item, similarity)) is not None:
        story = await session.get(Story, story_id)
    if story is None:
        story = Story(key=keys[0] if keys else f"item:{item.id}", title=item.title_zh or item.title,
                      first_seen_at=item.first_seen_at, last_seen_at=item.first_seen_at)
        session.add(story)
        await session.flush()
    item.story_id = story.id
    await session.flush()
    await refresh_story(session, story)
    return story


async def refresh_story(session: AsyncSession, story: Story) -> None:
    members = (await session.scalars(
        select(Item).where(Item.story_id == story.id, Item.status == "analyzed")
    )).all()
    if not members:
        return
    lead = min(members, key=lambda m: (TIER_RANK.get(m.tier, 9), -(m.score or 0), m.id))
    await session.execute(
        update(Item).where(Item.story_id == story.id).values(is_story_lead=(Item.id == lead.id))
    )
    story.title = lead.title_zh or lead.title
    story.item_count = len(members)
    story.source_count = len({m.source_id for m in members})
    story.first_seen_at = min(m.first_seen_at for m in members)
    story.last_seen_at = max(m.first_seen_at for m in members)
    story.status = "active"


def heat_of(first_seen_by_source: list[datetime], now: datetime) -> float:
    """独立来源计数 + 24h 半衰期：同一来源重复报道只算一次（取其最近一次）。"""
    return round(sum(
        0.5 ** (max((now - t).total_seconds(), 0) / 3600 / HEAT_HALF_LIFE_H) for t in first_seen_by_source
    ) * 10, 2)


async def recompute_heat(session: AsyncSession, *, window: timedelta = timedelta(hours=72)) -> int:
    now = datetime.now(UTC)
    rows = (await session.execute(
        select(Item.story_id, Item.source_id, func.max(Item.first_seen_at).label("t"))
        .join(Story, Story.id == Item.story_id)
        .where(Story.last_seen_at >= now - window, Item.status == "analyzed")
        .group_by(Item.story_id, Item.source_id)
    )).all()
    per_story: dict[int | None, list[datetime]] = {}
    for story_id, _source_id, seen_at in rows:
        per_story.setdefault(story_id, []).append(seen_at)
    for story_id, times in per_story.items():
        if story_id is not None:
            await session.execute(update(Story).where(Story.id == story_id).values(heat=heat_of(times, now)))
    # 超出窗口的事件热度归零、状态沉淀
    await session.execute(
        update(Story).where(Story.last_seen_at < now - window, Story.status == "active")
        .values(heat=0, status="settled")
    )
    await session.commit()
    return len(per_story)
