"""Operational watchdog for timer health checks."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select

from core.config import settings
from models import schema
from models.database import SessionLocal, init_db


def evaluate_health(
    db,
    *,
    now: datetime,
    max_success_age_hours: int = 3,
    max_article_age_hours: int = 6,
    grace: bool = False,
) -> dict:
    stale_cutoff = now - timedelta(hours=2)
    stale = db.scalars(
        select(schema.JobRun).where(schema.JobRun.status == "running", schema.JobRun.started_at < stale_cutoff)
    ).all()
    for job in stale:
        job.status = "failed"
        job.finished_at = now
        job.error_summary = "watchdog marked stale running job failed"
    db.commit()

    latest_ok = db.scalar(
        select(func.max(schema.JobRun.finished_at)).where(schema.JobRun.status.in_(("ok", "degraded")))
    )
    latest_article = db.scalar(select(func.max(schema.Article.ingested_at)))
    failures: list[str] = []
    if latest_ok is None:
        failures.append("no_success_history")
    elif latest_ok < now - timedelta(hours=max_success_age_hours):
        failures.append("latest_success_stale")
    if latest_article is None:
        failures.append("no_article_history")
    elif latest_article < now - timedelta(hours=max_article_age_hours):
        failures.append("latest_article_stale")
    if stale:
        failures.append("stale_running_jobs_marked_failed")

    no_history_only = set(failures) <= {"no_success_history", "no_article_history"}
    status = "ok"
    exit_code = 0
    if failures and not (grace and no_history_only):
        status = "failed"
        exit_code = 2
    elif failures:
        status = "no_history_grace"

    return {
        "status": status,
        "exit_code": exit_code,
        "failures": failures,
        "stale_jobs_marked_failed": len(stale),
        "latest_ok_job_at": latest_ok.isoformat() if latest_ok else None,
        "latest_article_at": latest_article.isoformat() if latest_article else None,
    }


def _send_alert(report: dict) -> None:
    if report["exit_code"] == 0 or not settings.feishu_webhook_url:
        return
    text = "E-AI watchdog failed: " + ", ".join(report["failures"])
    try:
        httpx.post(settings.feishu_webhook_url, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check production job/article freshness")
    parser.add_argument("--max-success-age-hours", type=int, default=3)
    parser.add_argument("--max-article-age-hours", type=int, default=6)
    parser.add_argument("--grace", action="store_true")
    args = parser.parse_args(argv)

    init_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        report = evaluate_health(
            db,
            now=now,
            max_success_age_hours=args.max_success_age_hours,
            max_article_age_hours=args.max_article_age_hours,
            grace=args.grace,
        )
        _send_alert(report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["exit_code"]:
            raise SystemExit(report["exit_code"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
