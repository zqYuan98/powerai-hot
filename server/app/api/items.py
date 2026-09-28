"""信息流、条目详情、搜索。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal, or_, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import card_query, decode_cursor, encode_cursor, fetch_cards, to_card
from app.db import get_session
from app.llm.client import LlmError, embed
from app.models import Item, Story
from app.models.enums import Channel, ItemStatus
from app.schemas.dto import Dims, ItemCard, ItemDetail, ItemPatch, Page, StoryBrief

router = APIRouter(prefix="/items", tags=["items"])
Session = Annotated[AsyncSession, Depends(get_session)]
TITLE_EXPR = func.coalesce(Item.title_zh, "") + literal(" ") + Item.title  # 与 trgm 索引表达式一致


@router.get("", response_model=Page[ItemCard])
async def list_items(
    session: Session,
    view: Literal["selected", "all", "starred", "screened"] = "selected",
    channel: Channel | None = None,
    province: str | None = None,
    source_id: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Page[ItemCard]:
    stmt = card_query()
    if view == "selected":
        stmt = stmt.where(Item.selected, Item.is_story_lead)
    elif view == "all":
        stmt = stmt.where(Item.status == ItemStatus.ANALYZED, Item.is_story_lead)
    elif view == "starred":
        stmt = stmt.where(Item.starred_at.is_not(None))
    else:  # screened：被淘汰/失败的条目，用于回溯误杀
        stmt = stmt.where(Item.status.in_((ItemStatus.SCREENED_OUT, ItemStatus.FAILED)))
    if channel:
        stmt = stmt.where(Item.channel == channel)
    if province:
        stmt = stmt.where(Item.province == province)
    if source_id:
        stmt = stmt.where(Item.source_id == source_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(TITLE_EXPR.ilike(pattern), Item.summary.ilike(pattern)))
    if cursor:
        ts, last_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(Item.first_seen_at, Item.id) < tuple_(literal(ts), literal(last_id)))
    stmt = stmt.order_by(Item.first_seen_at.desc(), Item.id.desc()).limit(limit + 1)
    cards = await fetch_cards(session, stmt)
    next_cursor = None
    if len(cards) > limit:
        cards = cards[:limit]
        next_cursor = encode_cursor(cards[-1].first_seen_at, cards[-1].id)
    return Page(items=cards, next_cursor=next_cursor)


@router.get("/search", response_model=list[ItemCard])
async def search(session: Session, q: Annotated[str, Query(min_length=1, max_length=100)],
                 limit: Annotated[int, Query(ge=1, le=50)] = 30) -> list[ItemCard]:
    """关键词（pg_trgm 加速）+ 语义（pgvector）混合检索，关键词命中优先。"""
    base = card_query().where(Item.status == ItemStatus.ANALYZED)
    pattern = f"%{q.strip()}%"
    keyword = await fetch_cards(session, base.where(
        or_(TITLE_EXPR.ilike(pattern), Item.summary.ilike(pattern))
    ).order_by(Item.first_seen_at.desc()).limit(limit))
    seen = {c.id for c in keyword}
    semantic: list[ItemCard] = []
    try:
        vectors = await embed([q])
    except LlmError:
        vectors = None
    if vectors:
        distance = Item.embedding.cosine_distance(vectors[0])
        semantic = await fetch_cards(session, base.where(Item.embedding.is_not(None), distance < 0.5)
                                     .order_by(distance).limit(limit))
    return (keyword + [c for c in semantic if c.id not in seen])[:limit]


@router.get("/{item_id}", response_model=ItemDetail)
async def get_item(session: Session, item_id: int) -> ItemDetail:
    row = (await session.execute(card_query().where(Item.id == item_id))).first()
    if row is None:
        raise HTTPException(404, "条目不存在")
    item, source_count = row[0], row[1]
    card = to_card(item, source_count)
    story = await session.get(Story, item.story_id) if item.story_id else None
    related: list[ItemCard] = []
    if story is not None:
        related = await fetch_cards(session, card_query().where(
            Item.story_id == story.id, Item.id != item.id, Item.status == ItemStatus.ANALYZED
        ).order_by(Item.first_seen_at.desc()).limit(20))
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
        await session.commit()
    return ItemDetail(
        **card.model_dump(),
        content_html=item.content_html,
        content_text=None if item.content_html else item.content_text,
        note=item.note,
        status=item.status,
        status_reason=item.status_reason,
        dims=Dims(relevance=item.d_relevance, opportunity=item.d_opportunity, certainty=item.d_certainty,
                  timeliness=item.d_timeliness, impact=item.d_impact),
        story=StoryBrief.model_validate(story) if story else None,
        related=related,
    )


@router.patch("/{item_id}", response_model=ItemCard)
async def patch_item(session: Session, item_id: int, body: ItemPatch) -> ItemCard:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "条目不存在")
    now = datetime.now(UTC)
    if body.starred is not None:
        item.starred_at = (item.starred_at or now) if body.starred else None
    if body.read is not None:
        item.read_at = (item.read_at or now) if body.read else None
    if body.note is not None:
        item.note = body.note or None
    await session.commit()
    row = (await session.execute(card_query().where(Item.id == item_id))).one()
    return to_card(row[0], row[1])

