"""PostgreSQL 持久任务队列。

- enqueue：dedupe_key 相同且仍在 queued/running 的任务只保留一个（部分唯一索引保证）。
- claim：FOR UPDATE SKIP LOCKED，多个消费者互不阻塞。
- 心跳超时的 running 任务由 recover_stale 重新排队（进程崩溃/重启不丢任务）。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.models.enums import JobStatus

# 与迁移中 ux_jobs_active_dedupe 的 WHERE 条件保持一致
ACTIVE_DEDUPE_PREDICATE = text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')")


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    dedupe_key: str | None = None,
    priority: int = 0,
    max_attempts: int = 3,
    delay: timedelta | None = None,
) -> int | None:
    """返回新任务 id；同 dedupe_key 的任务已在排队/执行时返回 None。调用方负责提交。"""
    stmt = insert(Job).values(
        kind=kind,
        payload=payload or {},
        dedupe_key=dedupe_key,
        priority=priority,
        max_attempts=max_attempts,
        run_after=datetime.now(UTC) + (delay or timedelta()),
    )
    if dedupe_key is not None:
        # 谓词必须是字面量：写成绑定参数时 PostgreSQL 无法据此推断部分唯一索引
        # （通用执行计划下报「no unique or exclusion constraint matching」）
        stmt = stmt.on_conflict_do_nothing(index_elements=[Job.dedupe_key], index_where=ACTIVE_DEDUPE_PREDICATE)
    return (await session.execute(stmt.returning(Job.id))).scalar_one_or_none()


async def claim(session: AsyncSession, worker_id: str, kinds: tuple[str, ...] | None = None) -> Job | None:
    now = datetime.now(UTC)
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED, Job.run_after <= now)
        .order_by(Job.priority.desc(), Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if kinds:
        stmt = stmt.where(Job.kind.in_(kinds))
    job = (await session.scalars(stmt)).first()
    if job is None:
        await session.rollback()
        return None
    job.status = JobStatus.RUNNING
    job.locked_by = worker_id
    job.heartbeat_at = now
    job.attempts += 1
    await session.commit()
    return job


async def heartbeat(session: AsyncSession, job_id: int) -> None:
    await session.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=datetime.now(UTC)))
    await session.commit()


async def complete(session: AsyncSession, job: Job, result: dict[str, Any] | None = None) -> None:
    job.status = JobStatus.DONE
    job.result = result
    job.error = None
    job.finished_at = datetime.now(UTC)
    await session.commit()


async def fail(session: AsyncSession, job: Job, error: str, *, retryable: bool = True) -> None:
    job.error = error[:4000]
    job.locked_by = None
    if retryable and job.attempts < job.max_attempts:
        job.status = JobStatus.QUEUED
        job.run_after = datetime.now(UTC) + timedelta(seconds=min(60 * 2 ** job.attempts, 1800))
    else:
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(UTC)
    await session.commit()


async def recover_stale(session: AsyncSession, *, stale_after: timedelta = timedelta(minutes=10)) -> int:
    result = await session.execute(
        update(Job)
        .where(Job.status == JobStatus.RUNNING, Job.heartbeat_at < datetime.now(UTC) - stale_after)
        .values(status=JobStatus.QUEUED, locked_by=None, error="worker 心跳超时，已重新排队")
    )
    await session.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


async def purge_finished(session: AsyncSession, *, older_than: timedelta = timedelta(days=14)) -> None:
    await session.execute(
        text("DELETE FROM jobs WHERE status IN ('done', 'failed') AND finished_at < :t"),
        {"t": datetime.now(UTC) - older_than},
    )
    await session.commit()
