"""Scheduler contract tests: one in-process scheduler keeps fixed job semantics."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.config import settings
from scheduler import monitor


class _FakeJob:
    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.next_run_time = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)


class _FakeScheduler:
    def __init__(self, timezone: str) -> None:
        self.timezone = timezone
        self.added: list[tuple[object, str, dict]] = []
        self.started = False
        self.stopped = False

    def add_job(self, func, trigger: str, **kwargs) -> None:
        self.added.append((func, trigger, kwargs))

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool) -> None:
        assert wait is False
        self.stopped = True

    def get_jobs(self) -> list[_FakeJob]:
        return [_FakeJob(kwargs["id"]) for _, _, kwargs in self.added]


@pytest.fixture(autouse=True)
def _reset_monitor() -> None:
    monitor._scheduler = None
    yield
    monitor._scheduler = None


def test_start_monitor_preserves_fixed_schedule_and_catchup(monkeypatch) -> None:
    fake = _FakeScheduler("unused")
    monkeypatch.setattr(settings, "auto_crawl_enabled", True)
    monkeypatch.setattr(settings, "crawl_interval_hours", 2)
    monkeypatch.setattr(
        "apscheduler.schedulers.background.BackgroundScheduler",
        lambda timezone: fake,
    )

    monitor.start_monitor()

    assert fake.timezone == "unused"  # constructor replacement received the instance
    assert fake.started is True
    jobs = {kwargs["id"]: (trigger, kwargs) for _, trigger, kwargs in fake.added}
    assert set(jobs) == {"crawl", "papers", "digest", "weekly", "digest_catchup"}
    assert jobs["crawl"][0] == "interval"
    assert jobs["crawl"][1]["hours"] == 2
    assert (jobs["papers"][0], jobs["papers"][1]["hour"], jobs["papers"][1]["minute"]) == ("cron", 6, 0)
    assert (jobs["digest"][0], jobs["digest"][1]["hour"], jobs["digest"][1]["minute"]) == ("cron", 7, 0)
    assert (
        jobs["weekly"][0], jobs["weekly"][1]["day_of_week"],
        jobs["weekly"][1]["hour"], jobs["weekly"][1]["minute"],
    ) == ("cron", "mon", 8, 0)
    assert jobs["digest_catchup"][0] == "date"
    assert monitor.monitor_status()["running"] is True
    assert set(monitor.monitor_status()["next_runs"]) == {"crawl", "papers", "digest", "weekly"}

    monitor.stop_monitor()
    assert fake.stopped is True
    assert monitor.monitor_status()["running"] is False


def test_start_monitor_does_nothing_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auto_crawl_enabled", False)

    monitor.start_monitor()

    assert monitor.monitor_status()["enabled"] is False
    assert monitor.monitor_status()["running"] is False
    assert monitor.monitor_status()["next_runs"] == {}
