"""日报 / 周报。"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import card_query, fetch_cards
from app.auth import Admin
from app.db import get_session
from app.models import Digest, Item
from app.models.enums import DigestKind
from app.schemas.dto import DigestBrief, DigestDetail, DigestSection, ItemCard, Ok
from app.worker import queue

router = APIRouter(prefix="/digests", tags=["digests"])
admin_router = APIRouter(prefix="/digests", tags=["digests"])
Session = Annotated[AsyncSession, Depends(get_session)]


def digest_brief(d: Digest) -> DigestBrief:
    return DigestBrief(
        id=d.id, kind=d.kind, period_start=d.period_start, period_end=d.period_end,  # type: ignore[arg-type]
        issue_no=d.issue_no, title=d.title, lead_title=d.content.get("lead_title"),
        item_count=d.content.get("stats", {}).get("items", 0),
    )


@router.get("", response_model=list[DigestBrief])
async def list_digests(session: Session, kind: DigestKind = DigestKind.DAILY,
                       limit: Annotated[int, Query(ge=1, le=120)] = 60) -> list[DigestBrief]:
    rows = (await session.scalars(
        select(Digest).where(Digest.kind == kind).order_by(Digest.period_start.desc()).limit(limit)
    )).all()
    return [digest_brief(d) for d in rows]


@router.get("/{kind}/latest", response_model=DigestDetail)
async def latest_digest(session: Session, admin: Admin, kind: DigestKind) -> DigestDetail:
    d = (await session.scalars(
        select(Digest).where(Digest.kind == kind).order_by(Digest.period_start.desc()).limit(1)
    )).first()
    if d is None:
        raise HTTPException(404, "还没有生成过")
    return await digest_detail(session, d, private=admin)


@router.get("/{kind}/{period_start}", response_model=DigestDetail)
async def get_digest(session: Session, admin: Admin, kind: DigestKind, period_start: date) -> DigestDetail:
    d = (await session.scalars(
        select(Digest).where(Digest.kind == kind, Digest.period_start == period_start)
    )).first()
    if d is None:
        raise HTTPException(404, "该期不存在")
    return await digest_detail(session, d, private=admin)


@admin_router.post("/{kind}/generate", response_model=Ok)
async def generate(session: Session, kind: DigestKind, period_start: date) -> Ok:
    await queue.enqueue(session, "digest", {"kind": kind.value, "period_start": period_start.isoformat()},
                        dedupe_key=f"digest:{kind.value}:{period_start}", priority=3)
    await session.commit()
    return Ok(detail="已加入队列")


async def digest_detail(session: AsyncSession, d: Digest, *, private: bool = False) -> DigestDetail:
    content = d.content
    ids = [i for sec in content.get("sections", []) for i in sec["item_ids"]]
    cards: dict[int, ItemCard] = {}
    if ids:
        cards = {c.id: c for c in await fetch_cards(session, card_query().where(Item.id.in_(ids)), private=private)}
    sections = [
        DigestSection(name=sec["name"], comment=sec.get("comment", ""),
                      items=[cards[i] for i in sec["item_ids"] if i in cards])
        for sec in content.get("sections", [])
    ]
    return DigestDetail(
        **digest_brief(d).model_dump(),
        overview=content.get("overview"),
        lead=cards.get(content.get("lead_id") or 0),
        sections=sections,
        stats=content.get("stats", {}),
        markdown=d.markdown,
    )
