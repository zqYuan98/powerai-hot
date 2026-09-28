"""worker 进程：定时器只负责「往队列里放任务」，消费者负责执行。

python -m app.worker.main

单实例保证：启动时拿 PostgreSQL 会话级 advisory lock，拿不到直接退出——
不会再出现旧版「两套调度器各跑一遍」的问题。
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import socket
from datetime import date, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.collectors.http import PoliteClient
from app.config import settings
from app.db import SessionLocal, engine
from app.logs import setup_logging
from app.models.enums import DigestKind
from app.worker import queue
from app.worker.jobs import HANDLERS

log = logging.getLogger("worker")
WORKER_LOCK_ID = 7_420_000
CONSUMERS = 3
HEARTBEAT_S = 30


async def put(kind: str, payload: dict[str, Any] | None = None, *, dedupe_key: str | None = None,
              priority: int = 0) -> None:
    async with SessionLocal() as session:
        await queue.enqueue(session, kind, payload, dedupe_key=dedupe_key or kind, priority=priority)
        await session.commit()


async def put_digest(kind: DigestKind) -> None:
    today = datetime.now(settings.tz).date()
    start = today if kind == DigestKind.DAILY else today - timedelta(days=today.weekday())
    await put("digest", {"kind": kind.value, "period_start": start.isoformat()},
              dedupe_key=f"digest:{kind.value}:{start}", priority=3)


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=settings.tz)
    every = sched.add_job
    every(put, "interval", minutes=1, args=["schedule_collect"], id="schedule_collect")
    every(put, "interval", minutes=15, args=["retry_failed"], id="retry_failed")
    every(put, "interval", minutes=30, args=["heat"], id="heat")
    every(put, "interval", minutes=30, args=["story_digests"], id="story_digests")
    every(put, "interval", minutes=10, args=["maintenance"], id="maintenance")
    every(put_digest, "cron", hour=8, minute=0, args=[DigestKind.DAILY], id="daily")
    every(put_digest, "cron", day_of_week="mon", hour=8, minute=30, args=[DigestKind.WEEKLY], id="weekly")
    every(put, "cron", hour="9,16", minute=5, args=["deadline_reminders"], id="deadlines")
    every(put, "cron", hour=3, minute=30, args=["backup"], id="backup")
    return sched


async def _beat(job_id: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), HEARTBEAT_S)
        if not stop.is_set():
            async with SessionLocal() as s:
                await queue.heartbeat(s, job_id)


async def run_one(worker_id: str, client: PoliteClient) -> bool:
    """认领并执行一个任务；队列为空返回 False。"""
    async with SessionLocal() as session:
        job = await queue.claim(session, worker_id)
        if job is None:
            return False
        handler = HANDLERS.get(job.kind)
        if handler is None:
            await queue.fail(session, job, f"未知任务类型 {job.kind}", retryable=False)
            return True
        done = asyncio.Event()
        beat = asyncio.create_task(_beat(job.id, done))
        try:
            async with SessionLocal() as work_session:
                result = await handler(work_session, client, job.payload)
        except Exception as exc:
            log.exception("任务失败 %s#%s", job.kind, job.id)
            await queue.fail(session, job, f"{type(exc).__name__}: {exc}")
        else:
            await queue.complete(session, job, result)
            log.info("任务完成 %s#%s %s", job.kind, job.id, result)
        finally:
            done.set()
            await beat
        return True


async def consume(worker_id: str, client: PoliteClient, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            busy = await run_one(worker_id, client)
        except Exception:
            log.exception("消费循环异常")
            busy = False
        if not busy:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), 2)


async def main() -> None:
    setup_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows 不支持
            loop.add_signal_handler(sig, stop.set)

    async with engine.connect() as lock_conn:
        got = await lock_conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKER_LOCK_ID})
        if not got:
            log.error("已有 worker 在运行（advisory lock 被占用），本进程退出")
            return
        sched = build_scheduler() if settings.worker_enabled_schedules else None
        if sched:
            sched.start()
        async with SessionLocal() as s:
            await queue.recover_stale(s, stale_after=timedelta(seconds=0))  # 上次异常退出遗留的 running
        base = f"{socket.gethostname()}:{date.today():%m%d}"
        log.info("worker 启动，%d 个消费者", CONSUMERS)
        async with PoliteClient() as client:
            try:
                await asyncio.gather(*(consume(f"{base}#{n}", client, stop) for n in range(CONSUMERS)))
            finally:
                if sched:
                    sched.shutdown(wait=False)
    await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
