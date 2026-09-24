"""Short-lived durable job worker."""
from __future__ import annotations

import argparse
import json
import socket
from datetime import timedelta
from typing import Callable

from sqlalchemy.orm import Session

from jobs.queue import claim_jobs, complete_job, fail_job
from models.database import SessionLocal, init_db

Handler = Callable[[Session, dict], dict | None]


def _crawl(db: Session, payload: dict) -> dict:
    from services.ingest import ingest_once

    return ingest_once(
        db,
        limit=max(1, min(int(payload.get("limit", 15)), 50)),
        group=str(payload.get("group", "all")),
    )


def _weekly(_db: Session, payload: dict) -> dict:
    from services.research import generate_weekly

    generate_weekly(int(payload["report_id"]))
    return {"report_id": int(payload["report_id"])}


def _topic(_db: Session, payload: dict) -> dict:
    from services.research import generate_topic

    generate_topic(int(payload["report_id"]))
    return {"report_id": int(payload["report_id"])}


def _card(_db: Session, payload: dict) -> dict:
    from services.cards import generate_card

    generate_card(int(payload["card_id"]))
    return {"card_id": int(payload["card_id"])}


def _digest(db: Session, _payload: dict) -> dict:
    from services.digest import build_daily_digest

    report = build_daily_digest(db)
    return {"report_id": report.id, "title": report.title}


HANDLERS: dict[str, Handler] = {
    "manual_crawl": _crawl,
    "scheduled_crawl": _crawl,
    "weekly_report_generate": _weekly,
    "topic_report_generate": _topic,
    "card_generate": _card,
    "card_retry": _card,
    "favorite_card_generate": _card,
    "daily_digest_generate": _digest,
}


def run_once(db: Session, *, worker_id: str, limit: int = 5) -> int:
    jobs = claim_jobs(db, worker_id=worker_id, limit=limit)
    for job in jobs:
        handler = HANDLERS.get(job.job_type)
        if handler is None:
            fail_job(
                db,
                job,
                error_type="unknown_job_type",
                error_message=f"no handler registered for {job.job_type}",
            )
            continue
        try:
            result = handler(db, dict(job.payload_json or {}))
            complete_job(db, job, result=result)
        except Exception as exc:
            db.rollback()
            retryable = isinstance(exc, (TimeoutError, ConnectionError, OSError))
            delay = timedelta(seconds=min(900, 30 * (2 ** max(0, job.attempt_count - 1)))) if retryable else None
            fail_job(
                db,
                job,
                error_type=type(exc).__name__,
                error_message=str(exc),
                retry_delay=delay,
            )
    return len(jobs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-oneshot")
    args = parser.parse_args(argv)
    init_db()
    db = SessionLocal()
    try:
        processed = run_once(db, worker_id=args.worker_id, limit=args.limit)
        print(json.dumps({"processed": processed, "worker_id": args.worker_id}))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
