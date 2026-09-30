"""公开 REST API v1：匿名只读，给 Agent、脚本和第三方工具用。

复用站内接口的查询逻辑，但一律按访客视角（不含个人数据），并转换成 schemas/public.py 的稳定契约。
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import digests, items, knowledge, leads, stories
from app.core.ratelimit import SEARCH_LIMIT, client_ip
from app.db import get_session
from app.models.enums import BizLine, Channel, DigestKind, KnowledgeDomain, KnowledgeType, Stage
from app.schemas.public import (
    V1Digest,
    V1DigestBrief,
    V1HotStory,
    V1Item,
    V1ItemPage,
    V1KnowledgePage,
    V1LeadPage,
    V1Story,
    v1_digest,
    v1_digest_brief,
    v1_hot,
    v1_item,
    v1_knowledge,
    v1_story,
)

router = APIRouter(prefix="/v1", tags=["v1"])
Session = Annotated[AsyncSession, Depends(get_session)]
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


@router.get("/items", response_model=V1ItemPage, summary="最近的精选或全部动态")
async def v1_items(
    session: Session,
    mode: Literal["selected", "all"] = "selected",
    window: Literal["24h", "7d"] = "24h",
    channel: Channel | None = None,
    q: Annotated[str | None, Query(max_length=100, description="标题或摘要包含的关键词")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> V1ItemPage:
    page = await items.list_items(session, admin=False, view=mode, channel=channel, province=None, source_id=None,
                                  q=q, since=datetime.now(UTC) - WINDOWS[window], cursor=cursor, limit=limit)
    return V1ItemPage(items=[v1_item(c) for c in page.items], next_cursor=page.next_cursor)


@router.get("/search", response_model=list[V1Item], summary="按关键词与语义搜索全部已精读条目")
async def v1_search(request: Request, session: Session, q: Annotated[str, Query(min_length=1, max_length=100)],
                    limit: Annotated[int, Query(ge=1, le=20)] = 10) -> list[V1Item]:
    SEARCH_LIMIT.check(client_ip(request))
    return [v1_item(c) for c in await items.search_cards(session, q, limit)]


@router.get("/leads", response_model=V1LeadPage, summary="结构化商机（招标、中标、项目、规划）")
async def v1_leads(
    session: Session,
    stage: Stage | None = None,
    province: Annotated[str | None, Query(max_length=16)] = None,
    biz_line: BizLine | None = None,
    open_only: Annotated[bool, Query(description="只看未截止（无截止时间的也保留）")] = False,
    min_amount_wan: Decimal | None = None,
    min_voltage_kv: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Literal["recent", "deadline", "amount"] = "recent",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> V1LeadPage:
    page = await leads.list_leads(
        session, admin=False, stage=[stage] if stage else None, province=[province] if province else None,
        biz_line=[biz_line] if biz_line else None, follow=None, min_amount_wan=min_amount_wan,
        min_voltage_kv=min_voltage_kv, open_only=open_only, q=q, sort=sort, offset=offset, limit=limit,
    )
    return V1LeadPage(items=[v1_item(r.item) for r in page.items], total=page.total)


@router.get("/hot", response_model=list[V1HotStory], summary="当前热点事件（按独立信源数与时间衰减排序）")
async def v1_hot_stories(session: Session, limit: Annotated[int, Query(ge=1, le=10)] = 10) -> list[V1HotStory]:
    return [v1_hot(h) for h in await stories.hot(session, admin=False, hours=48, limit=limit)]


@router.get("/stories/{story_id}", response_model=V1Story, summary="一个事件的时间线与 AI 综述")
async def v1_story_detail(session: Session, story_id: int) -> V1Story:
    return v1_story(await stories.story_detail(session, admin=False, story_id=story_id))


@router.get("/knowledge", response_model=V1KnowledgePage, summary="电力基建知识库：公众号与专业网站文章的知识卡片")
async def v1_knowledge_list(
    session: Session,
    domain: KnowledgeDomain | None = None,
    ktype: KnowledgeType | None = None,
    q: Annotated[str | None, Query(max_length=100, description="标题、摘要、要点、标签包含的关键词")] = None,
    sort: Literal["score", "recent"] = "score",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> V1KnowledgePage:
    page = await knowledge.list_knowledge(session, admin=False, domain=domain, ktype=ktype, q=q, featured=False,
                                          sort=sort, status=None, offset=offset, limit=limit)
    return V1KnowledgePage(items=[v1_knowledge(k) for k in page.items], total=page.total)


@router.get("/dailies", response_model=list[V1DigestBrief], summary="日报 / 周报目录")
async def v1_dailies(session: Session, kind: DigestKind = DigestKind.DAILY,
                     limit: Annotated[int, Query(ge=1, le=60)] = 30) -> list[V1DigestBrief]:
    return [v1_digest_brief(d) for d in await digests.list_digests(session, kind=kind, limit=limit)]


@router.get("/dailies/latest", response_model=V1Digest, summary="最新一期日报 / 周报")
async def v1_daily_latest(session: Session, kind: DigestKind = DigestKind.DAILY) -> V1Digest:
    return v1_digest(await digests.latest_digest(session, admin=False, kind=kind))


@router.get("/dailies/{day}", response_model=V1Digest, summary="指定日期的日报 / 周报")
async def v1_daily(session: Session, day: date, kind: DigestKind = DigestKind.DAILY) -> V1Digest:
    return v1_digest(await digests.get_digest(session, admin=False, kind=kind, period_start=day))
