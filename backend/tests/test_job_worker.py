from jobs.queue import enqueue_job
from jobs.worker import run_once


def test_worker_completes_registered_job(db, monkeypatch):
    seen = []
    monkeypatch.setitem(
        __import__("jobs.worker", fromlist=["HANDLERS"]).HANDLERS,
        "test_job",
        lambda _db, payload: seen.append(payload) or {"ok": True},
    )
    job = enqueue_job(db, "test_job", {"value": 7}, idempotency_key="test:7")

    processed = run_once(db, worker_id="worker-test", limit=1)

    assert processed == 1
    assert seen == [{"value": 7}]
    assert job.status == "completed"
    assert job.result_json == {"ok": True}


def test_worker_requeues_retryable_failure(db, monkeypatch):
    def fail(_db, _payload):
        raise TimeoutError("temporary")

    monkeypatch.setitem(
        __import__("jobs.worker", fromlist=["HANDLERS"]).HANDLERS,
        "test_retry",
        fail,
    )
    job = enqueue_job(db, "test_retry", {}, idempotency_key="retry:1")

    run_once(db, worker_id="worker-test", limit=1)

    assert job.status == "queued"
    assert job.error_type == "TimeoutError"
    assert job.available_at is not None
