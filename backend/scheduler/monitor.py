"""内置定时监控 —— 进程内自动采集，无需 Redis / Celery。

启动后：先延迟若干秒采一次（让用户立刻看到数据），之后每隔 N 小时自动采集。
可用环境变量 AUTO_CRAWL_ENABLED / CRAWL_INTERVAL_HOURS 控制。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from core.config import settings
from models.database import SessionLocal
from services.ingest import ingest_once

log = logging.getLogger("monitor")

_scheduler = None
_last_run: dict | None = None


def _job() -> None:
    _run_group("news")


def _papers_job() -> None:
    _run_group("papers")


def _digest_job() -> None:
    db = SessionLocal()
    try:
        from services.digest import build_daily_digest

        r = build_daily_digest(db)
        log.info("今日精选已生成：%s（%s 条）", r.title, (r.content_json or {}).get("total", 0))
    except Exception as e:
        log.warning("今日精选生成失败：%s", e)
    finally:
        db.close()


def _digest_catchup_job() -> None:
    """开机补生成：07:00 的 cron 只在进程活着时触发，本地后端常在白天才启动，
    当天日报会静默缺失。启动后检查一次，缺了就补（零 LLM、幂等，代价可忽略）。"""
    now = datetime.now()
    if now.hour < 7:
        return  # 尚未到当日生成时刻，留给 07:00 的 cron
    db = SessionLocal()
    try:
        from sqlalchemy import select

        from models import schema

        title = f"今日精选 · {now:%Y-%m-%d}"
        exists = db.scalar(
            select(schema.Report).where(schema.Report.type == "daily", schema.Report.title == title)
        )
        if exists is None:
            _digest_job()
    finally:
        db.close()


def _weekly_job() -> None:
    db = SessionLocal()
    try:
        from services.research import create_weekly

        rid = create_weekly(db).id
    finally:
        db.close()
    from services.research import generate_weekly

    generate_weekly(rid)  # 调度线程内同步生成即可


def _run_group(group: str) -> None:
    global _last_run
    db = SessionLocal()
    try:
        stats = ingest_once(db, limit=20, group=group)
        _last_run = {"at": datetime.now().isoformat(timespec="seconds"), "group": group, **stats}
        log.info("自动采集完成：%s", _last_run)
    except Exception as e:  # 监控不能因单次失败而崩
        _last_run = {"at": datetime.now().isoformat(timespec="seconds"), "group": group, "error": str(e)}
        log.warning("自动采集失败：%s", e)
    finally:
        db.close()


def start_monitor() -> None:
    global _scheduler
    if not settings.auto_crawl_enabled:
        log.info("自动采集已关闭（AUTO_CRAWL_ENABLED=false）")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.warning("未安装 APScheduler，跳过定时监控。pip install APScheduler 后生效。")
        return

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        _job,
        trigger="interval",
        hours=max(1, settings.crawl_interval_hours),
        id="crawl",
        next_run_time=datetime.now() + timedelta(seconds=15),  # 启动后 ~15s 采一次
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _papers_job,
        trigger="cron",
        hour=6,
        minute=0,
        id="papers",
        next_run_time=datetime.now() + timedelta(seconds=60),
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _digest_job,
        trigger="cron",
        hour=7,
        minute=0,
        id="digest",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _weekly_job,
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _digest_catchup_job,
        trigger="date",
        run_date=datetime.now() + timedelta(seconds=45),
        id="digest_catchup",
    )
    _scheduler.start()
    log.info("定时监控已启动：资讯每 %s 小时，论文每日 06:00，日报每日 07:00，周报每周一 08:00", settings.crawl_interval_hours)


def stop_monitor() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


_JOB_LABELS = {"crawl": "资讯采集", "papers": "论文采集", "digest": "今日精选", "weekly": "周报"}


def next_run_times() -> dict[str, str]:
    """各定时任务的下次触发时间（本地时区 ISO），调度未启动时为空。"""
    if _scheduler is None:
        return {}
    out: dict[str, str] = {}
    for job in _scheduler.get_jobs():
        if job.id in _JOB_LABELS and job.next_run_time:
            out[job.id] = job.next_run_time.isoformat(timespec="seconds")
    return out


def monitor_status() -> dict:
    return {
        "enabled": settings.auto_crawl_enabled,
        "interval_hours": settings.crawl_interval_hours,
        "running": _scheduler is not None,
        "last_run": _last_run,
        "next_runs": next_run_times(),
    }
