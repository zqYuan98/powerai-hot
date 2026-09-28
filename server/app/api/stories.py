"""热点榜与事件时间线。热度 = 独立来源数 × 24h 半衰期，与质量评分是两套体系。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import card_query, fetch_cards
from app.db import get_session
from app.models import Item, Story
from app.models.enums import ItemStatus
from app.schemas.dto import HotStory, StoryBrief, StoryDetail

router = APIRouter(tags=["stories"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/hot", response_model=list[HotStory])
async def hot(session: Session, hours: Annotated[int, Query(ge=6, le=168)] = 48,
              limit: Annotated[int, Query(ge=1, le=30)] = 10) -> list[HotStory]:
    now = datetime.now(UTC)
    stories = (await session.scalars(
        select(Story).where(Story.last_seen_at >= now - timedelta(hours=hours), Story.heat > 0)
        .order_by(Story.heat.desc(), Story.last_seen_at.desc()).limit(limit)
    )).all()
    if not stories:
        return []
    cards = await fetch_cards(session, card_query().where(
        Item.story_id.in_([s.id for s in stories]), Item.is_story_lead, Item.status == ItemStatus.ANALYZED
    ))
    lead_by_story = {c.story_id: c for c in cards}
    out: list[HotStory] = []
    for story in stories:
        if (card := lead_by_story.get(story.id)) is None:
            continue
        out.append(HotStory(
            rank=len(out) + 1, story=StoryBrief.model_validate(story), lead_item=card,
            first_seen_at=story.first_seen_at, last_seen_at=story.last_seen_at,
            is_new=story.first_seen_at >= now - timedelta(hours=6),
        ))
    return out


@router.get("/stories/{story_id}", response_model=StoryDetail)
async def story_detail(session: Session, story_id: int) -> StoryDetail:
    story = await session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "事件不存在")
    timeline = await fetch_cards(session, card_query().where(
        Item.story_id == story_id, Item.status == ItemStatus.ANALYZED
    ).order_by(Item.first_seen_at.asc(), Item.id.asc()))
    return StoryDetail(story=StoryBrief.model_validate(story), digest=story.digest,
                       first_seen_at=story.first_seen_at, last_seen_at=story.last_seen_at, timeline=timeline)
