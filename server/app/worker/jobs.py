"""任务处理器：kind → async handler(session, client, payload) -> result dict。"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.http import PoliteClient
from app.config import settings
from app.digest.builder import build_digest
from app.llm.client import LlmError, complete_json, load_prompt
from app.models import Article, Feedback, GoldLabel, Item, Source, Story
from app.models.enums import ArticleStatus, DigestKind, ItemStatus
from app.pipeline import knowledge
from app.pipeline.collect import collect_source, due_sources
from app.pipeline.evaluate import run_eval
from app.pipeline.llm_schemas import StoryDigestOutput
from app.pipeline.notify import format_feedback, remind_deadlines, send_feishu
from app.pipeline.process import MAX_ATTEMPTS, process_items
from app.pipeline.stories import recompute_heat
from app.pipeline.tuning import load_tuning
from app.worker import queue

log = logging.getLogger(__name__)
Handler = Callable[[AsyncSession, PoliteClient, dict[str, Any]], Awaitable[dict[str, Any]]]
HANDLERS: dict[str, Handler] = {}
PROCESS_BATCH = 15


def handler(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn
    return deco


async def enqueue_articles(session: AsyncSession, article_ids: list[int], *, priority: int = 1) -> int:
    for aid in article_ids:
        await queue.enqueue(session, "article_process", {"article_id": aid}, priority=priority,
                            dedupe_key=f"article:{aid}")
    return len(article_ids)


async def enqueue_process(session: AsyncSession, item_ids: list[int], *, priority: int = 0) -> int:
    n = 0
    for start in range(0, len(item_ids), PROCESS_BATCH):
        batch = item_ids[start:start + PROCESS_BATCH]
        await queue.enqueue(session, "process", {"item_ids": batch}, priority=priority,
                            dedupe_key=f"process:{batch[0]}-{batch[-1]}")
        n += 1
    return n


@handler("collect")
async def collect_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    source = await session.get(Source, payload["source_id"])
    if source is None:
        return {"skipped": "信源不存在"}
    if not source.enabled and not payload.get("force"):
        return {"skipped": "信源已停用"}
    outcome = await collect_source(session, client, source)
    if outcome.knowledge:
        batches = await enqueue_articles(session, outcome.new_ids)
    else:
        batches = await enqueue_process(session, outcome.new_ids, priority=1)
    await session.commit()
    return {**asdict(outcome), "new_ids": len(outcome.new_ids), "process_batches": batches}


@handler("process")
async def process_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    stats = await process_items(session, client, payload["item_ids"])
    return asdict(stats)


@handler("schedule_collect")
async def schedule_collect(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    sources = await due_sources(session)
    for s in sources:
        await queue.enqueue(session, "collect", {"source_id": s.id}, dedupe_key=f"collect:{s.key}", priority=2)
    await session.commit()
    return {"enqueued": [s.key for s in sources]}


@handler("retry_failed")
async def retry_failed(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    """重新排队可重试的失败条目，以及因 worker 中断而滞留在 new 状态的条目。"""
    cutoff = datetime.now(UTC) - timedelta(minutes=30)
    ids = list((await session.scalars(
        select(Item.id).where(
            ((Item.status == ItemStatus.FAILED) & (Item.attempts < MAX_ATTEMPTS))
            | ((Item.status == ItemStatus.NEW) & (Item.first_seen_at < cutoff))
        ).order_by(Item.id).limit(300)
    )).all())
    batches = await enqueue_process(session, ids)
    article_ids = list((await session.scalars(
        select(Article.id).where(
            ((Article.status == ArticleStatus.FAILED) & (Article.attempts < knowledge.MAX_ATTEMPTS))
            | ((Article.status == ArticleStatus.NEW) & (Article.created_at < cutoff))
        ).order_by(Article.id).limit(100)
    )).all())
    await enqueue_articles(session, article_ids, priority=0)
    await session.commit()
    return {"items": len(ids), "batches": batches, "articles": len(article_ids)}


@handler("article_process")
async def article_process(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    return await knowledge.process_article(session, client, payload["article_id"])


@handler("heat")
async def heat_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    return {"stories": await recompute_heat(session)}


@handler("story_digests")
async def story_digests(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    """为多来源事件生成/更新 AI 综述（报道数变化才重写）。"""
    if not settings.llm_enabled:
        return {"skipped": "未配置 LLM"}
    stories = (await session.scalars(
        select(Story).where(Story.status == "active", Story.item_count >= 2,
                            Story.item_count != Story.digest_item_count)
        .order_by(Story.heat.desc()).limit(20)
    )).all()
    done = 0
    for story in stories:
        members = (await session.scalars(
            select(Item).where(Item.story_id == story.id, Item.status == ItemStatus.ANALYZED)
            .order_by(Item.first_seen_at).limit(12)
        )).all()
        material = "\n".join(
            f"- {m.first_seen_at:%Y-%m-%d} {m.source.name}：{m.title_zh or m.title}。{m.summary or ''}" for m in members
        )
        try:
            out = await complete_json(task="story_digest", model=settings.llm_model_pro,
                                      system=load_prompt("story_digest"), user=material,
                                      schema=StoryDigestOutput, max_tokens=1200, reasoning="low")
        except LlmError as exc:
            log.warning("事件综述失败 story=%s：%s", story.id, exc)
            continue
        story.digest = out.digest.strip()
        story.digest_item_count = story.item_count
        await session.commit()
        done += 1
    return {"written": done}


@handler("digest")
async def digest_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    kind = DigestKind(payload["kind"])
    digest = await build_digest(session, kind, date.fromisoformat(payload["period_start"]))
    return {"digest_id": digest.id, "items": digest.content["stats"]["items"]}


@handler("deadline_reminders")
async def deadline_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    return {"sent": await remind_deadlines(session, await load_tuning(session))}


@handler("feedback_notify")
async def feedback_notify(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    fb = await session.get(Feedback, payload["feedback_id"])
    if fb is None:
        return {"skipped": "反馈不存在"}
    await send_feishu(format_feedback(fb))  # 失败抛出，由队列重试
    return {"sent": True}


@handler("maintenance")
async def maintenance(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    recovered = await queue.recover_stale(session)
    await queue.purge_finished(session)
    # 被初筛淘汰超过 60 天的条目只留标题，释放正文空间（有人工标注的留着，评测重跑要用）
    await session.execute(
        update(Item).where(Item.status == ItemStatus.SCREENED_OUT,
                           Item.first_seen_at < datetime.now(UTC) - timedelta(days=60),
                           Item.content_text.is_not(None), ~Item.id.in_(select(GoldLabel.item_id)))
        .values(content_text=None, content_html=None)
    )
    await session.commit()
    return {"recovered_jobs": recovered}


@handler("eval")
async def eval_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    run = await run_eval(session, mode=payload.get("mode", "stored"), split=payload.get("split", "development"),
                         label=payload.get("label"))
    return {"run_id": run.id, "status": run.status, "error": run.error}


@handler("backup")
async def backup_job(session: AsyncSession, client: PoliteClient, payload: dict[str, Any]) -> dict[str, Any]:
    """pg_dump 自定义格式备份，保留 N 天。"""
    url = urlsplit(settings.database_url.replace("+asyncpg", ""))
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.backup_dir / f"powerai-{datetime.now(settings.tz):%Y%m%d-%H%M}.dump"
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    cmd = ["pg_dump", "-Fc", "-h", url.hostname or "localhost", "-p", str(url.port or 5432),
           "-U", url.username or "postgres", "-d", url.path.lstrip("/"), "-f", str(target)]
    proc = await asyncio.to_thread(subprocess.run, cmd, env=env, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump 失败：{proc.stderr[:500]}")
    cutoff = datetime.now().timestamp() - settings.backup_keep_days * 86400
    removed = 0
    for f in settings.backup_dir.glob("powerai-*.dump"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    return {"file": target.name, "bytes": target.stat().st_size, "removed": removed}
