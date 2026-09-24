from datetime import UTC, datetime, timedelta

from jobs.queue import claim_jobs, complete_job, enqueue_job, fail_job, recover_stale_jobs
from models import schema


def test_enqueue_job_is_idempotent_for_same_key(db):
    first = enqueue_job(db, "manual_crawl", {"source": "all"}, idempotency_key="crawl:all:1")
    second = enqueue_job(db, "manual_crawl", {"source": "all"}, idempotency_key="crawl:all:1")

    assert first.id == second.id
    assert db.query(schema.PersistentJob).count() == 1


def test_claim_jobs_uses_priority_then_creation_order(db):
    enqueue_job(db, "card_generate", {"id": 1}, idempotency_key="card:1", priority=1)
    high = enqueue_job(db, "manual_crawl", {}, idempotency_key="crawl:1", priority=10)

    claimed = claim_jobs(db, worker_id="worker-a", limit=1)

    assert [job.id for job in claimed] == [high.id]
    assert claimed[0].status == "running"
    assert claimed[0].worker_id == "worker-a"
    assert claimed[0].attempt_count == 1
    assert claimed[0].heartbeat_at is not None


def test_fail_job_retries_with_delay_then_becomes_terminal(db):
    job = enqueue_job(
        db,
        "article_fulltext_backfill",
        {},
        idempotency_key="backfill:1",
        max_attempts=2,
    )
    claimed = claim_jobs(db, worker_id="worker-a", limit=1)[0]
    now = datetime.now(UTC).replace(tzinfo=None)

    fail_job(db, claimed, error_type="timeout", error_message="temporary", retry_delay=timedelta(seconds=30), now=now)
    assert job.status == "queued"
    assert job.available_at == now + timedelta(seconds=30)

    claimed = claim_jobs(db, worker_id="worker-a", limit=1, now=now + timedelta(seconds=31))[0]
    fail_job(db, claimed, error_type="timeout", error_message="again", retry_delay=timedelta(seconds=30), now=now)
    assert job.status == "failed"
    assert job.finished_at == now


def test_complete_and_recover_stale_jobs(db):
    completed = enqueue_job(db, "card_generate", {}, idempotency_key="card:2")
    claimed = claim_jobs(db, worker_id="worker-a", limit=1)[0]
    complete_job(db, claimed, result={"card_id": 2})
    assert completed.status == "completed"
    assert completed.result_json == {"card_id": 2}

    stale = enqueue_job(db, "scheduled_crawl", {}, idempotency_key="crawl:stale")
    claimed_stale = claim_jobs(db, worker_id="worker-b", limit=1)[0]
    claimed_stale.heartbeat_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
    db.commit()

    recovered = recover_stale_jobs(
        db,
        stale_before=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
    )
    assert recovered == 1
    assert stale.status == "queued"
    assert stale.worker_id is None
