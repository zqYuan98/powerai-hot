from jobs.queue import enqueue_job


def test_admin_can_read_and_retry_failed_job(admin_client, db):
    job = enqueue_job(db, "manual_crawl", {"group": "all"}, idempotency_key="crawl:api")
    job.status = "failed"
    job.error_type = "timeout"
    job.error_message = "temporary"
    db.commit()

    detail = admin_client.get(f"/api/admin/jobs/{job.id}")
    assert detail.status_code == 200
    assert detail.json()["job_type"] == "manual_crawl"
    assert detail.json()["error_type"] == "timeout"

    retried = admin_client.post(f"/api/admin/jobs/{job.id}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"


def test_workspace_user_cannot_access_job_status(client, db):
    job = enqueue_job(db, "manual_crawl", {}, idempotency_key="crawl:private")

    response = client.get(f"/api/admin/jobs/{job.id}")

    assert response.status_code in {401, 403}
