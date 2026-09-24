"""Production system status endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import schema
from models.database import get_db

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def system_status(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = now - timedelta(hours=24)
    latest_jobs = db.scalars(
        select(schema.JobRun).order_by(schema.JobRun.started_at.desc(), schema.JobRun.id.desc()).limit(10)
    ).all()
    total_processed = int(db.scalar(
        select(func.count()).select_from(schema.Article)
        .where(schema.Article.processing_status == "processed")
    ) or 0)
    degraded = int(db.scalar(
        select(func.count()).select_from(schema.Article)
        .where(schema.Article.scored_by.in_(("fallback_model", "rule")))
    ) or 0)
    latest_article = db.scalar(select(func.max(schema.Article.ingested_at)))
    failures = db.execute(
        select(schema.Source.name, schema.SourceRun.transport_status, schema.SourceRun.parse_status, schema.SourceRun.error_summary)
        .join(schema.SourceRun, schema.SourceRun.source_id == schema.Source.id)
        .where(
            (schema.SourceRun.transport_status != "ok") |
            (schema.SourceRun.parse_status.in_(("schema_error", "parse_error")))
        )
        .order_by(schema.SourceRun.attempted_at.desc())
        .limit(10)
    ).all()
    return {
        "server_time": now.isoformat(),
        "latest_jobs": [
            {
                "run_key": job.run_key,
                "job_name": job.job_name,
                "status": job.status,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "fetched": job.fetched,
                "inserted": job.inserted,
                "selected": job.selected,
                "source_failures": job.source_failures,
            }
            for job in latest_jobs
        ],
        "freshness": {
            "latest_ingested_at": latest_article.isoformat() if latest_article else None,
            "added_24h": int(db.scalar(
                select(func.count()).select_from(schema.Article)
                .where(schema.Article.ingested_at >= day_ago)
            ) or 0),
        },
        "degradation": {
            "processed": total_processed,
            "fallback_or_rule": degraded,
            "ratio": round(degraded / total_processed, 4) if total_processed else 0,
        },
        "failed_sources": [
            {"name": name, "transport_status": transport, "parse_status": parse, "error_summary": error}
            for name, transport, parse, error in failures
        ],
    }
