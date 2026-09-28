"""处理一批新条目：正文回捞 → 规则 → LLM① 初筛 → LLM② 精读 → 向量 → 归并 → 推送。

LLM 调用并发执行但不碰数据库会话；写库在单个会话里顺序完成。
模型失败的条目标记 failed（可重试的留待重试，配置类故障直接挂起等人工处理），绝不用规则分冒充。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors.fulltext import fetch_fulltext, selectors_for
from app.collectors.http import PoliteClient
from app.llm.client import LlmError, embed
from app.models import Item
from app.models.enums import Channel, ItemStatus
from app.pipeline.analyze import analyze_item, apply_analysis, screen_batch
from app.pipeline.notify import notify_item
from app.pipeline.rules import hard_noise, rule_channel
from app.pipeline.stories import assign_story
from app.pipeline.tuning import Tuning, load_tuning

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
TRUSTED_CATEGORIES = {Channel.TENDER.value, Channel.AWARD.value}


@dataclass
class ProcessStats:
    total: int = 0
    fulltext: int = 0
    screened_out: int = 0
    analyzed: int = 0
    selected: int = 0
    failed: int = 0
    notified: int = 0
    errors: list[str] = field(default_factory=list)


def _mark_failed(item: Item, err: LlmError | Exception, stats: ProcessStats) -> None:
    item.status = ItemStatus.FAILED.value
    item.status_reason = str(err)[:500]
    retryable = isinstance(err, LlmError) and err.retryable
    item.attempts = item.attempts + 1 if retryable else MAX_ATTEMPTS  # 配置类故障不自动重试
    stats.failed += 1
    if len(stats.errors) < 5:
        stats.errors.append(item.status_reason)


def _trusted(item: Item) -> bool:
    """招标平台类信源内容天然与电力相关，跳过初筛。"""
    return item.source.category in TRUSTED_CATEGORIES or bool(item.source.config.get("trusted"))


async def _fill_fulltext(client: PoliteClient, items: list[Item], stats: ProcessStats) -> None:
    targets = [
        i for i in items
        if not i.content_text and selectors_for(i.url, i.source.config.get("fulltext_selectors"))
    ]
    results = await asyncio.gather(*(
        fetch_fulltext(client, i.url, i.source.config.get("fulltext_selectors")) for i in targets
    ))
    for item, ft in zip(targets, results, strict=True):
        if ft is not None:
            item.content_text, item.content_html = ft.text, ft.html
            stats.fulltext += 1


async def _screen(items: list[Item], tuning: Tuning, stats: ProcessStats) -> list[Item]:
    survivors: list[Item] = []
    to_screen: list[Item] = []
    for item in items:
        if reason := hard_noise(item.title):
            item.status, item.status_reason = ItemStatus.SCREENED_OUT.value, reason
            stats.screened_out += 1
        elif _trusted(item):
            survivors.append(item)
        else:
            to_screen.append(item)
    for start in range(0, len(to_screen), 15):
        batch = to_screen[start:start + 15]
        try:
            verdicts = await screen_batch(batch, tuning.profile)
        except LlmError as exc:
            for item in batch:
                _mark_failed(item, exc, stats)
            continue
        for item in batch:
            v = verdicts[item.id]
            if v.relevant:
                item.channel = (rule_channel(item.title) or Channel(v.channel)).value
                item.province = v.province
                survivors.append(item)
            else:
                item.status = ItemStatus.SCREENED_OUT.value
                item.status_reason = f"初筛：{v.reason or '与电力基建无关'}"
                stats.screened_out += 1
    return survivors


async def _embed(items: list[Item]) -> None:
    texts = [f"{i.title_zh or i.title}\n{i.summary or ''}" for i in items]
    try:
        vectors = await embed(texts)
    except LlmError as exc:
        log.warning("向量化失败，本批跳过向量归并：%s", exc)
        return
    if vectors:
        for item, vec in zip(items, vectors, strict=True):
            item.embedding = vec


async def process_items(session: AsyncSession, client: PoliteClient, item_ids: list[int]) -> ProcessStats:
    tuning = await load_tuning(session)
    items = list((await session.scalars(
        select(Item).options(selectinload(Item.lead))
        .where(Item.id.in_(item_ids), Item.status.in_((ItemStatus.NEW, ItemStatus.FAILED)),
               Item.attempts < MAX_ATTEMPTS)
        .order_by(Item.id)
    )).all())
    stats = ProcessStats(total=len(items))
    if not items:
        return stats

    await _fill_fulltext(client, items, stats)
    survivors = await _screen(items, tuning, stats)
    await session.commit()

    outputs = await asyncio.gather(*(analyze_item(i, tuning.profile) for i in survivors), return_exceptions=True)
    analyzed: list[Item] = []
    for item, out in zip(survivors, outputs, strict=True):
        if isinstance(out, BaseException):
            _mark_failed(item, out if isinstance(out, Exception) else RuntimeError(str(out)), stats)
            continue
        lead = apply_analysis(item, out, tuning)
        if lead is not None:
            item.lead = lead
            session.add(lead)
        analyzed.append(item)
        stats.analyzed += 1
        stats.selected += int(item.selected)
    await session.commit()

    if analyzed:
        await _embed(analyzed)
        for item in analyzed:
            await assign_story(session, item, similarity=tuning.story_similarity)
            await session.commit()  # 逐条提交，尽快释放归并锁
        for item in analyzed:
            if item.is_story_lead:
                stats.notified += await notify_item(session, item, tuning)
    return stats
