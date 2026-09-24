from __future__ import annotations

from datetime import datetime, timedelta

from jobs.watchdog import evaluate_health
from models import schema


NOW = datetime(2026, 7, 17, 8, 0, 0)


def test_watchdog_health_is_zero_when_recent_success_and_article(db):
    db.add(schema.JobRun(run_key="news:ok", job_name="ingest-news", status="ok", started_at=NOW, finished_at=NOW))
    db.add(schema.Article(title="fresh", url_hash="fresh", ingested_at=NOW - timedelta(minutes=10)))
    db.commit()

    report = evaluate_health(db, now=NOW, max_success_age_hours=2, max_article_age_hours=3)

    assert report["exit_code"] == 0
    assert report["status"] == "ok"


def test_watchdog_fails_when_latest_success_or_article_is_stale(db):
    db.add(schema.JobRun(run_key="news:old", job_name="ingest-news", status="ok", started_at=NOW - timedelta(hours=5), finished_at=NOW - timedelta(hours=5)))
    db.add(schema.Article(title="old", url_hash="old", ingested_at=NOW - timedelta(hours=6)))
    db.commit()

    report = evaluate_health(db, now=NOW, max_success_age_hours=2, max_article_age_hours=3)

    assert report["exit_code"] == 2
    assert "latest_success_stale" in report["failures"]
    assert "latest_article_stale" in report["failures"]


def test_watchdog_initial_deploy_without_history_uses_grace(db):
    report = evaluate_health(db, now=NOW, max_success_age_hours=2, max_article_age_hours=3, grace=True)

    assert report["exit_code"] == 0
    assert report["status"] == "no_history_grace"


def test_watchdog_initial_deploy_without_grace_fails(db):
    report = evaluate_health(db, now=NOW, max_success_age_hours=2, max_article_age_hours=3, grace=False)

    assert report["exit_code"] == 2
    assert "no_success_history" in report["failures"]
    assert "no_article_history" in report["failures"]
