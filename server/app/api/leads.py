"""商机看板：结构化筛选 + 个人跟进状态。"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, nulls_last, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import card_query, fetch_cards
from app.api.items import TITLE_EXPR
from app.db import get_session
from app.models import Item, Lead
from app.models.enums import BizLine, FollowStatus, ItemStatus, Stage
from app.schemas.dto import LeadOut, LeadPage, LeadPatch, LeadRow

router = APIRouter(prefix="/leads", tags=["leads"])
Session = Annotated[AsyncSession, Depends(get_session)]

SORTS: dict[str, tuple[Any, ...]] = {
    "recent": (Item.first_seen_at.desc(), Item.id.desc()),
    "deadline": (nulls_last(Lead.deadline_at.asc()), Item.id.desc()),
    "amount": (nulls_last(Lead.amount_wan.desc()), Item.id.desc()),
    "match": (Lead.match_score.desc(), Item.first_seen_at.desc()),
}


@router.get("", response_model=LeadPage)
async def list_leads(
    session: Session,
    stage: Annotated[list[Stage] | None, Query()] = None,
    province: Annotated[list[str] | None, Query()] = None,
    biz_line: Annotated[list[BizLine] | None, Query()] = None,
    follow: Annotated[list[FollowStatus] | None, Query()] = None,
    min_amount_wan: Decimal | None = None,
    min_voltage_kv: int | None = None,
    open_only: bool = False,  # 只看未截止
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Literal["recent", "deadline", "amount", "match"] = "recent",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LeadPage:
    conds = [Item.status == ItemStatus.ANALYZED]
    if stage:
        conds.append(Lead.stage.in_(stage))
    if province:
        conds.append(Lead.province.in_(province))
    if biz_line:
        conds.append(Lead.biz_line.in_(biz_line))
    conds.append(Lead.follow_status.in_(follow) if follow else Lead.follow_status != FollowStatus.IGNORED)
    if min_amount_wan is not None:
        conds.append(Lead.amount_wan >= min_amount_wan)
    if min_voltage_kv is not None:
        conds.append(Lead.voltage_kv >= min_voltage_kv)
    if open_only:
        conds.append(or_(Lead.deadline_at.is_(None), Lead.deadline_at >= datetime.now(UTC)))
    if q:
        pattern = f"%{q.strip()}%"
        conds.append(or_(TITLE_EXPR.ilike(pattern), Lead.project_name.ilike(pattern), Lead.owner.ilike(pattern)))

    total = await session.scalar(select(func.count()).select_from(Lead).join(Item).where(*conds)) or 0
    cards = await fetch_cards(session, card_query().join(Lead, Lead.item_id == Item.id).where(*conds)
                              .order_by(*SORTS[sort]).offset(offset).limit(limit))
    return LeadPage(items=[LeadRow(item=c, lead=c.lead) for c in cards if c.lead], total=total)


@router.get("/provinces", response_model=list[str])
async def lead_provinces(session: Session) -> list[str]:
    rows = await session.scalars(
        select(Lead.province).where(Lead.province.is_not(None)).group_by(Lead.province)
        .order_by(func.count().desc())
    )
    return [p for p in rows if p]


@router.patch("/{item_id}", response_model=LeadOut)
async def patch_lead(session: Session, item_id: int, body: LeadPatch) -> LeadOut:
    lead = await session.get(Lead, item_id)
    if lead is None:
        raise HTTPException(404, "商机不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await session.commit()
    await session.refresh(lead)
    return LeadOut.model_validate(lead)
