"""路由共用：游标编解码、ORM → 卡片序列化。

private=False（访客）时抹掉管理员的个人数据：收藏、已读、商机跟进状态与备注。
"""
from __future__ import annotations

import base64
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Item, Lead, Story
from app.models.enums import FollowStatus
from app.schemas.dto import ItemCard, LeadOut, SourceBrief


def encode_cursor(ts: datetime, item_id: int) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{item_id}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, item_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(ts), int(item_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "无效的游标") from exc


def to_lead(lead: Lead, *, private: bool = False) -> LeadOut:
    out = LeadOut.model_validate(lead)
    if private:
        return out
    return out.model_copy(update={"follow_status": FollowStatus.NEW, "follow_note": None, "remind_at": None})


def to_card(item: Item, source_count: int | None = None, *, private: bool = False) -> ItemCard:
    return ItemCard(
        id=item.id,
        title=item.title,
        title_zh=item.title_zh,
        url=item.url,
        source=SourceBrief.model_validate(item.source),
        tier=item.tier,
        channel=item.channel,  # type: ignore[arg-type]
        province=item.province,
        summary=item.summary,
        reason=item.reason,
        action=item.action,
        tags=item.tags or [],
        score=item.score,
        selected=item.selected,
        published_at=item.published_at,
        first_seen_at=item.first_seen_at,
        story_id=item.story_id,
        also_reported=max((source_count or 1) - 1, 0),
        starred=private and item.starred_at is not None,
        read=private and item.read_at is not None,
        lead=to_lead(item.lead, private=private) if item.lead else None,
    )


def card_query() -> Select[Item, int]:
    """条目 + 所属事件的来源数（用于「另有 N 家信源报道」）。"""
    return (
        select(Item, Story.source_count)
        .outerjoin(Story, Story.id == Item.story_id)
        .options(selectinload(Item.lead))
    )


async def fetch_cards(session: AsyncSession, stmt: Select[Item, int], *, private: bool = False) -> list[ItemCard]:
    rows = (await session.execute(stmt)).all()
    return [to_card(item, count, private=private) for item, count in rows]
