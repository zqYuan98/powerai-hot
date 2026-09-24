"""Administrative inspection and retry endpoints for durable jobs."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import schema
from models.database import get_db

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


def _out(job: schema.PersistentJob) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "priority": job.priority,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "available_at": job.available_at.isoformat() if job.available_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "result": job.result_json,
        "error_type": job.error_type,
        "error_message": job.error_message,
    }


@router.get("")
def list_jobs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(schema.PersistentJob)
        .order_by(schema.PersistentJob.id.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [_out(job) for job in rows]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(schema.PersistentJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return _out(job)


@router.post("/{job_id}/retry", status_code=202)
def retry_job(job_id: int, response: Response, db: Session = Depends(get_db)):
    job = db.get(schema.PersistentJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status not in {"failed", "completed"}:
        raise HTTPException(409, "job is not retryable")
    job.status = "queued"
    job.available_at = datetime.now(UTC).replace(tzinfo=None)
    job.started_at = None
    job.finished_at = None
    job.heartbeat_at = None
    job.worker_id = None
    job.error_type = None
    job.error_message = None
    db.commit()
    response.headers["Location"] = f"/api/admin/jobs/{job.id}"
    return _out(job)
