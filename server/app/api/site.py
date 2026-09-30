"""站点公共接口：概况、访客反馈；反馈的查看与处理在后台。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth_required
from app.config import settings
from app.core.ratelimit import FEEDBACK_LIMIT, client_ip
from app.db import get_session
from app.models import Feedback, Item, Source
from app.models.enums import CHANNEL_LABELS, Channel
from app.schemas.dto import ChannelCount, FeedbackAck, FeedbackIn, FeedbackOut, FeedbackPatch, Meta
from app.worker import queue

router = APIRouter(tags=["site"])
admin_router = APIRouter(tags=["site"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/meta", response_model=Meta)
async def meta(session: Session) -> Meta:
    today = datetime.now(settings.tz).replace(hour=0, minute=0, second=0, microsecond=0)
    counts = dict((await session.execute(
        select(Item.channel, func.count()).where(Item.selected, Item.is_story_lead, Item.first_seen_at >= today)
        .group_by(Item.channel)
    )).all())
    return Meta(
        channels=[ChannelCount(channel=c, label=CHANNEL_LABELS[c], today=counts.get(c.value, 0)) for c in Channel],
        last_collect_at=await session.scalar(select(func.max(Source.last_ok_at))),
        sources_enabled=await session.scalar(select(func.count()).select_from(Source).where(Source.enabled)) or 0,
        llm_enabled=settings.llm_enabled,
        embedding_enabled=settings.embedding_enabled,
        push_enabled=bool(settings.feishu_webhook_url),
        auth_required=auth_required(),
    )


@router.post("/site/feedback", response_model=FeedbackAck, status_code=201)
async def submit_feedback(request: Request, session: Session, body: FeedbackIn) -> FeedbackAck:
    ip = client_ip(request)
    FEEDBACK_LIMIT.check(ip)
    fb = Feedback(content=body.content, contact=body.contact or None, page_url=body.page_url or None, ip=ip,
                  user_agent=(request.headers.get("user-agent") or "")[:300] or None)
    session.add(fb)
    await session.flush()
    if settings.feishu_webhook_url:
        await queue.enqueue(session, "feedback_notify", {"feedback_id": fb.id}, priority=2)
    await session.commit()
    return FeedbackAck(id=fb.id)


@admin_router.get("/feedback", response_model=list[FeedbackOut])
async def list_feedback(session: Session, status: Literal["new", "done"] | None = None,
                        limit: Annotated[int, Query(ge=1, le=200)] = 100) -> list[FeedbackOut]:
    stmt = select(Feedback).order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Feedback.status == status)
    return [FeedbackOut.model_validate(f) for f in await session.scalars(stmt)]


@admin_router.patch("/feedback/{feedback_id}", response_model=FeedbackOut)
async def patch_feedback(session: Session, feedback_id: int, body: FeedbackPatch) -> FeedbackOut:
    fb = await session.get(Feedback, feedback_id)
    if fb is None:
        raise HTTPException(404, "反馈不存在")
    fb.status = body.status
    await session.commit()
    return FeedbackOut.model_validate(fb)
