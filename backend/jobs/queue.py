"""Durable database-backed job queue primitives."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.schema import PersistentJob


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
    priority: int = 0,
    max_attempts: int = 3,
    available_at: datetime | None = None,
    created_by: str | None = None,
) -> PersistentJob:
    existing = db.scalar(
        select(PersistentJob).where(PersistentJob.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    job = PersistentJob(
        job_type=job_type,
        payload_json=payload,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
        available_at=available_at or _utcnow(),
        created_by=created_by,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(PersistentJob).where(PersistentJob.idempotency_key == idempotency_key)
        )
        if existing is None:
            raise
        return existing
    db.refresh(job)
    return job


def claim_jobs(
    db: Session,
    *,
    worker_id: str,
    limit: int = 1,
    now: datetime | None = None,
) -> list[PersistentJob]:
    claim_time = now or _utcnow()
    stmt = (
        select(PersistentJob)
        .where(
            PersistentJob.status == "queued",
            PersistentJob.available_at <= claim_time,
        )
        .order_by(
            PersistentJob.priority.desc(),
            PersistentJob.created_at.asc(),
            PersistentJob.id.asc(),
        )
        .limit(max(1, min(limit, 100)))
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    jobs = list(db.scalars(stmt).all())
    for job in jobs:
        job.status = "running"
        job.worker_id = worker_id
        job.started_at = claim_time
        job.heartbeat_at = claim_time
        job.attempt_count += 1
        job.error_type = None
        job.error_message = None
    db.commit()
    return jobs


def heartbeat_job(db: Session, job: PersistentJob, *, now: datetime | None = None) -> None:
    job.heartbeat_at = now or _utcnow()
    db.commit()


def complete_job(
    db: Session,
    job: PersistentJob,
    *,
    result: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    finished_at = now or _utcnow()
    job.status = "completed"
    job.result_json = result
    job.finished_at = finished_at
    job.heartbeat_at = finished_at
    db.commit()


def fail_job(
    db: Session,
    job: PersistentJob,
    *,
    error_type: str,
    error_message: str,
    retry_delay: timedelta | None = None,
    now: datetime | None = None,
) -> None:
    failure_time = now or _utcnow()
    job.error_type = error_type[:80]
    job.error_message = error_message[:4000]
    job.worker_id = None
    if retry_delay is not None and job.attempt_count < job.max_attempts:
        job.status = "queued"
        job.available_at = failure_time + retry_delay
        job.started_at = None
        job.heartbeat_at = None
    else:
        job.status = "failed"
        job.finished_at = failure_time
        job.heartbeat_at = failure_time
    db.commit()


def recover_stale_jobs(
    db: Session,
    *,
    stale_before: datetime,
    now: datetime | None = None,
) -> int:
    jobs = list(
        db.scalars(
            select(PersistentJob).where(
                PersistentJob.status == "running",
                PersistentJob.heartbeat_at < stale_before,
            )
        ).all()
    )
    recovered_at = now or _utcnow()
    for job in jobs:
        job.status = "queued" if job.attempt_count < job.max_attempts else "failed"
        job.worker_id = None
        job.started_at = None
        job.heartbeat_at = None
        job.available_at = recovered_at
        job.error_type = "stale_heartbeat"
        job.error_message = "worker heartbeat expired"
        if job.status == "failed":
            job.finished_at = recovered_at
    db.commit()
    return len(jobs)
