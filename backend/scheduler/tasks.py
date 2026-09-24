"""Celery 定时任务（可选）—— 与内置监控等价，用于需要分布式队列的部署。

本地默认走 scheduler/monitor.py 的进程内监控，无需 Redis。
"""
from celery import Celery

from core.config import settings
from models.database import SessionLocal
from services.ingest import ingest_once

celery_app = Celery("powerai_hot", broker=settings.celery_broker_url)
celery_app.conf.beat_schedule = {
    "crawl-all-sources": {
        "task": "scheduler.tasks.crawl_all",
        "schedule": settings.crawl_interval_hours * 3600.0,
    },
    "crawl-papers-daily": {
        "task": "scheduler.tasks.crawl_papers",
        "schedule": 24 * 3600.0,
    },
    "daily-digest": {
        "task": "scheduler.tasks.make_digest",
        "schedule": 24 * 3600.0,
    },
    "weekly-report": {
        "task": "scheduler.tasks.make_weekly",
        "schedule": 7 * 24 * 3600.0,
    },
}


@celery_app.task
def crawl_all() -> dict:
    """采集 → DeepSeek 分析打分 → 去重入库 → 阈值精选 → 命中订阅通知。"""
    db = SessionLocal()
    try:
        return ingest_once(db, limit=20, group="news")
    finally:
        db.close()


@celery_app.task
def crawl_papers() -> dict:
    db = SessionLocal()
    try:
        return ingest_once(db, limit=30, group="papers")
    finally:
        db.close()


@celery_app.task
def make_digest() -> dict:
    from services.digest import build_daily_digest

    db = SessionLocal()
    try:
        r = build_daily_digest(db)
        return {"id": r.id, "title": r.title}
    finally:
        db.close()


@celery_app.task
def make_weekly() -> dict:
    from services.research import create_weekly, generate_weekly

    db = SessionLocal()
    try:
        rid = create_weekly(db).id
    finally:
        db.close()
    generate_weekly(rid)
    return {"id": rid}
