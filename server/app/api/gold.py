"""精选校准：人工标注与评测记录。评测本身在 worker 里跑（重跑模式会调模型）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import EvalRun, GoldLabel, Item
from app.pipeline.evaluate import is_error, label_stats, next_case, save_label
from app.pipeline.tuning import load_tuning
from app.schemas.dto import (
    EvalRunBrief,
    EvalRunDetail,
    EvalRunIn,
    GoldCase,
    GoldLabelIn,
    GoldRecent,
    GoldStats,
    Ok,
)
from app.worker import queue

router = APIRouter(tags=["gold"])
Session = Annotated[AsyncSession, Depends(get_session)]
GOLD_TARGET = 150
BODY_CHARS = 2000


async def _stats(session: AsyncSession) -> GoldStats:
    counts = await label_stats(session)
    recent = (await session.execute(
        select(GoldLabel.item_id, Item.title, GoldLabel.decision, GoldLabel.labeled_at)
        .join(Item, Item.id == GoldLabel.item_id).order_by(GoldLabel.labeled_at.desc()).limit(8)
    )).all()
    return GoldStats(total=sum(counts["decision"].values()), target=GOLD_TARGET, **counts,
                     recent=[GoldRecent.model_validate(r._mapping) for r in recent])


def _case(item: Item, label: GoldLabel | None = None) -> GoldCase:
    body = (item.content_text or "").strip()
    return GoldCase(
        item_id=item.id, title=item.title, url=item.url, source_name=item.source.name, tier=item.tier,
        published_at=item.published_at, first_seen_at=item.first_seen_at,
        body=body[:BODY_CHARS] if body else None,
        decision=label.decision if label else None,  # type: ignore[arg-type]
        note=label.note if label else None,
    )


@router.get("/gold/stats", response_model=GoldStats)
async def gold_stats(session: Session) -> GoldStats:
    return await _stats(session)


@router.get("/gold/next", response_model=GoldCase | None)
async def gold_next(session: Session, skip: Annotated[list[int] | None, Query()] = None) -> GoldCase | None:
    item = await next_case(session, await load_tuning(session), skip)
    return _case(item) if item else None


@router.get("/gold/{item_id}", response_model=GoldCase)
async def gold_case(session: Session, item_id: int) -> GoldCase:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "条目不存在")
    return _case(item, await session.get(GoldLabel, item_id))


@router.put("/gold/{item_id}", response_model=GoldStats)
async def put_label(session: Session, item_id: int, body: GoldLabelIn) -> GoldStats:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "条目不存在")
    await save_label(session, item, body.decision, body.note)
    return await _stats(session)


@router.delete("/gold/{item_id}", response_model=GoldStats)
async def delete_label(session: Session, item_id: int) -> GoldStats:
    if label := await session.get(GoldLabel, item_id):
        await session.delete(label)
        await session.commit()
    return await _stats(session)


@router.get("/eval-runs", response_model=list[EvalRunBrief])
async def list_runs(session: Session, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[EvalRunBrief]:
    # 不取 cases/sweep 大字段
    rows = (await session.execute(
        select(EvalRun.id, EvalRun.label, EvalRun.mode, EvalRun.split, EvalRun.status, EvalRun.error,
               EvalRun.cost_yuan, EvalRun.created_at, EvalRun.finished_at,
               func.jsonb_build_object(
                   "n", EvalRun.metrics["n"], "total", EvalRun.metrics["total"],
                   "precision", EvalRun.metrics["precision"], "recall", EvalRun.metrics["recall"],
                   "f1", EvalRun.metrics["f1"], "accuracy", EvalRun.metrics["accuracy"],
               ).label("metrics"))
        .order_by(EvalRun.id.desc()).limit(limit)
    )).all()
    return [EvalRunBrief.model_validate(r._mapping) for r in rows]


@router.get("/eval-runs/{run_id}", response_model=EvalRunDetail)
async def get_run(session: Session, run_id: int) -> EvalRunDetail:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, "评测不存在")
    errors = sorted((c for c in run.cases if is_error(c)), key=lambda c: -(c["score"] or 0))
    return EvalRunDetail.model_validate({**EvalRunBrief.model_validate(run).model_dump(),
                                         "params": run.params, "sweep": run.sweep, "errors": errors})


@router.post("/eval-runs", response_model=Ok)
async def start_run(session: Session, body: EvalRunIn) -> Ok:
    job_id = await queue.enqueue(session, "eval", body.model_dump(), dedupe_key="eval", priority=3, max_attempts=1)
    await session.commit()
    return Ok(detail="评测已加入队列，完成后刷新本页" if job_id else "已有评测在进行中")
