"""补向量与重建事件归并：首次配置 Embedding、或调整归并阈值后执行一次。

python -m app.cli reindex
"""
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.llm.client import embed
from app.models import Item, Story
from app.models.enums import ItemStatus
from app.pipeline.stories import assign_story, recompute_heat
from app.pipeline.tuning import load_tuning

BATCH = 32


def embedding_text(item: Item) -> str:
    """与处理管线保持一致的向量化文本。"""
    return f"{item.title_zh or item.title}\n{item.summary or ''}"


async def backfill_embeddings(session: AsyncSession) -> int:
    done = 0
    while True:
        items = list((await session.scalars(
            select(Item).where(Item.status == ItemStatus.ANALYZED, Item.embedding.is_(None))
            .order_by(Item.id).limit(BATCH)
        )).all())
        if not items:
            return done
        vectors = await embed([embedding_text(i) for i in items])
        if vectors is None:  # 未配置 Embedding
            return done
        for item, vec in zip(items, vectors, strict=True):
            item.embedding = vec
        await session.commit()
        done += len(items)


async def rebuild_stories(session: AsyncSession) -> tuple[int, int]:
    """清空事件后按发现时间顺序重新归并。返回 (事件数, 多来源事件数)。"""
    tuning = await load_tuning(session)
    await session.execute(update(Item).values(story_id=None, is_story_lead=True))
    await session.execute(delete(Story))
    await session.commit()
    ids = list((await session.scalars(
        select(Item.id).where(Item.status == ItemStatus.ANALYZED).order_by(Item.first_seen_at, Item.id)
    )).all())
    for item_id in ids:
        item = await session.get(Item, item_id, options=[selectinload(Item.lead)])
        assert item is not None
        await assign_story(session, item, similarity=tuning.story_similarity)
        await session.commit()
    await recompute_heat(session)
    total = await session.scalar(select(func.count()).select_from(Story)) or 0
    multi = await session.scalar(select(func.count()).select_from(Story).where(Story.source_count > 1)) or 0
    return total, multi
