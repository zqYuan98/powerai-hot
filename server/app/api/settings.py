"""后台设置与运维（仅管理员）：信源健康、订阅规则、打分参数、模型用量、任务队列。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Item, Job, LlmCall, Source, SourceRun, WatchRule
from app.models.enums import ItemStatus, JobStatus
from app.pipeline.tuning import Tuning, load_tuning, save_tuning
from app.schemas.dto import (
    JobOut,
    Ok,
    PipelineStats,
    SourceOut,
    SourcePatch,
    SourceRunOut,
    UsageDay,
    UsageOut,
    WatchRuleIn,
    WatchRuleOut,
)
from app.worker import queue
from app.worker.jobs import enqueue_process

router = APIRouter(tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]


# ---------- 信源 ----------

@router.get("/sources", response_model=list[SourceOut])
async def list_sources(session: Session) -> list[SourceOut]:
    now = datetime.now(UTC)
    runs = {r.source_id: r for r in (await session.execute(
        select(SourceRun.source_id, func.count().label("runs"),
               func.sum(cast(SourceRun.transport_status.in_(("ok", "partial")), Integer)).label("ok"))
        .where(SourceRun.started_at >= now - timedelta(hours=24)).group_by(SourceRun.source_id)
    )).all()}
    items = {r.source_id: r for r in (await session.execute(
        select(Item.source_id, func.count().label("new"), func.sum(cast(Item.selected, Integer)).label("sel"))
        .where(Item.first_seen_at >= now - timedelta(days=7)).group_by(Item.source_id)
    )).all()}
    out = []
    for s in (await session.scalars(select(Source).order_by(Source.enabled.desc(), Source.tier, Source.key))).all():
        dto = SourceOut.model_validate(s)
        if r := runs.get(s.id):
            dto.runs_24h, dto.ok_24h = r.runs, r.ok or 0
        if i := items.get(s.id):
            dto.new_7d, dto.selected_7d = i.new, i.sel or 0
        out.append(dto)
    return out


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def patch_source(session: Session, source_id: int, body: SourcePatch) -> SourceOut:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "信源不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await session.commit()
    return SourceOut.model_validate(source)


@router.post("/sources/{source_id}/collect", response_model=Ok)
async def collect_now(session: Session, source_id: int) -> Ok:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "信源不存在")
    job_id = await queue.enqueue(session, "collect", {"source_id": source.id, "force": True},
                                 dedupe_key=f"collect:{source.key}", priority=5)
    await session.commit()
    return Ok(detail="已加入队列" if job_id else "该信源已在采集中")


@router.get("/sources/{source_id}/runs", response_model=list[SourceRunOut])
async def source_runs(session: Session, source_id: int,
                      limit: Annotated[int, Query(ge=1, le=100)] = 30) -> list[SourceRunOut]:
    rows = (await session.scalars(
        select(SourceRun).where(SourceRun.source_id == source_id).order_by(SourceRun.started_at.desc()).limit(limit)
    )).all()
    return [SourceRunOut.model_validate(r) for r in rows]


# ---------- 订阅规则 ----------

@router.get("/watch-rules", response_model=list[WatchRuleOut])
async def list_rules(session: Session) -> list[WatchRuleOut]:
    return [WatchRuleOut.model_validate(r) for r in (await session.scalars(select(WatchRule).order_by(WatchRule.id)))]


@router.post("/watch-rules", response_model=WatchRuleOut)
async def create_rule(session: Session, body: WatchRuleIn) -> WatchRuleOut:
    rule = WatchRule(**body.model_dump(mode="json"))
    session.add(rule)
    await session.commit()
    return WatchRuleOut.model_validate(rule)


@router.put("/watch-rules/{rule_id}", response_model=WatchRuleOut)
async def update_rule(session: Session, rule_id: int, body: WatchRuleIn) -> WatchRuleOut:
    rule = await session.get(WatchRule, rule_id)
    if rule is None:
        raise HTTPException(404, "规则不存在")
    for field, value in body.model_dump(mode="json").items():
        setattr(rule, field, value)
    await session.commit()
    return WatchRuleOut.model_validate(rule)


@router.delete("/watch-rules/{rule_id}", response_model=Ok)
async def delete_rule(session: Session, rule_id: int) -> Ok:
    rule = await session.get(WatchRule, rule_id)
    if rule is not None:
        await session.delete(rule)
        await session.commit()
    return Ok()


# ---------- 打分参数与画像 ----------

@router.get("/tuning", response_model=Tuning)
async def get_tuning(session: Session) -> Tuning:
    return await load_tuning(session)


@router.put("/tuning", response_model=Tuning)
async def put_tuning(session: Session, body: Tuning) -> Tuning:
    await save_tuning(session, body)
    return body


# ---------- 模型用量与流水线 ----------

@router.get("/usage", response_model=UsageOut)
async def usage(session: Session, days: Annotated[int, Query(ge=1, le=90)] = 14) -> UsageOut:
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date(func.timezone(settings.timezone, LlmCall.created_at))
    rows = (await session.execute(
        select(day.label("day"), LlmCall.task, func.count().label("calls"),
               func.sum(cast(~LlmCall.ok, Integer)).label("failures"),
               func.sum(LlmCall.prompt_tokens).label("pt"), func.sum(LlmCall.completion_tokens).label("ct"),
               func.sum(LlmCall.cost_yuan).label("cost"))
        .where(LlmCall.created_at >= since).group_by(day, LlmCall.task).order_by(day.desc(), LlmCall.task)
    )).all()
    errors = (await session.execute(
        select(LlmCall.created_at, LlmCall.task, LlmCall.model, LlmCall.error)
        .where(~LlmCall.ok, LlmCall.created_at >= since).order_by(LlmCall.created_at.desc()).limit(20)
    )).all()
    return UsageOut(
        days=[UsageDay(day=r.day, task=r.task, calls=r.calls, failures=r.failures or 0, prompt_tokens=r.pt or 0,
                       completion_tokens=r.ct or 0, cost_yuan=round(r.cost or 0, 4)) for r in rows],
        recent_errors=[dict(r._mapping) for r in errors],
    )


@router.get("/pipeline", response_model=PipelineStats)
async def pipeline_stats(session: Session) -> PipelineStats:
    since = datetime.now(UTC) - timedelta(hours=24)

    async def count(*conds: object) -> int:
        return await session.scalar(select(func.count()).select_from(Item).where(*conds)) or 0  # type: ignore[arg-type]

    job_counts = dict((await session.execute(
        select(Job.status, func.count()).where(Job.status.in_(("queued", "running"))).group_by(Job.status)
    )).all())
    return PipelineStats(
        items_24h=await count(Item.first_seen_at >= since),
        analyzed_24h=await count(Item.analyzed_at >= since),
        selected_24h=await count(Item.analyzed_at >= since, Item.selected),
        screened_out_24h=await count(Item.first_seen_at >= since, Item.status == ItemStatus.SCREENED_OUT),
        failed_pending=await count(Item.status == ItemStatus.FAILED),
        queued_jobs=job_counts.get(JobStatus.QUEUED.value, 0),
        running_jobs=job_counts.get(JobStatus.RUNNING.value, 0),
    )


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(session: Session, status: JobStatus | None = None,
                    limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[JobOut]:
    stmt = select(Job).order_by(Job.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Job.status == status)
    return [JobOut.model_validate(j) for j in (await session.scalars(stmt))]


@router.post("/items/retry-failed", response_model=Ok)
async def retry_failed_items(session: Session) -> Ok:
    """修好模型配置后，一键重试所有失败条目（包括配置类故障挂起的）。"""
    ids = list((await session.scalars(select(Item.id).where(Item.status == ItemStatus.FAILED))).all())
    if ids:
        await session.execute(update(Item).where(Item.id.in_(ids)).values(attempts=0))
        await enqueue_process(session, ids, priority=1)
        await session.commit()
    return Ok(detail=f"已重新排队 {len(ids)} 条")
