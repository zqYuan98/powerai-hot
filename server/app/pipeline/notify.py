"""订阅匹配与飞书推送。notifications 表的唯一约束保证不重复推送。"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors.textutil import CN_TZ
from app.config import settings
from app.models import Item, Lead, Notification, WatchRule
from app.models.enums import CHANNEL_LABELS
from app.pipeline.tuning import Tuning

log = logging.getLogger(__name__)


def rule_matches(rule: WatchRule, item: Item) -> bool:
    haystack = f"{item.title} {item.title_zh or ''} {item.summary or ''} {' '.join(item.tags or [])}"
    if rule.keywords and not any(k.casefold() in haystack.casefold() for k in rule.keywords):
        return False
    if rule.provinces and item.province not in rule.provinces:
        return False
    if rule.channels and item.channel not in rule.channels:
        return False
    lead = item.lead
    if rule.min_amount_wan is not None and (lead is None or lead.amount_wan is None
                                            or lead.amount_wan < rule.min_amount_wan):
        return False
    return rule.min_voltage_kv is None or (
        lead is not None and lead.voltage_kv is not None and lead.voltage_kv >= rule.min_voltage_kv
    )


def worth_pushing(item: Item, tuning: Tuning) -> bool:
    if item.selected:
        return True
    return item.lead is not None and item.lead.match_score >= tuning.lead_notify_min_match


def format_message(item: Item, headline: str) -> str:
    lines = [f"【{headline}】{item.title_zh or item.title}"]
    lead = item.lead
    if lead is not None:
        facts = [
            f"业主：{lead.owner}" if lead.owner else "",
            f"金额：{lead.amount_wan}万元" if lead.amount_wan else "",
            f"电压：{lead.voltage_kv}kV" if lead.voltage_kv else "",
            f"截止：{lead.deadline_at.astimezone(CN_TZ):%m-%d %H:%M}" if lead.deadline_at else "",
        ]
        if facts := [f for f in facts if f]:
            lines.append(" | ".join(facts))
    if item.summary:
        lines.append(item.summary)
    if item.action:
        lines.append(f"建议：{item.action}")
    lines.append(f"{CHANNEL_LABELS.get(item.channel, item.channel)} · {item.source.name} · 评分 {item.score:.0f}"
                 if item.score is not None else item.source.name)
    lines.append(f"{settings.public_base_url}/items/{item.id}")
    return "\n".join(lines)


async def send_feishu(text: str) -> None:
    if not settings.feishu_webhook_url:
        raise RuntimeError("未配置 FEISHU_WEBHOOK_URL")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.feishu_webhook_url, json={"msg_type": "text", "content": {"text": text}})
        resp.raise_for_status()
        body = resp.json()
        if body.get("code", 0) != 0:
            raise RuntimeError(f"飞书返回错误：{body}")


async def _claim(session: AsyncSession, item_id: int, rule_id: int | None, kind: str) -> int | None:
    """抢占一条推送记录；已推过返回 None。"""
    stmt = (insert(Notification).values(item_id=item_id, rule_id=rule_id, kind=kind)
            .on_conflict_do_nothing().returning(Notification.id))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _deliver(session: AsyncSession, notification_id: int, message: str) -> None:
    note = await session.get(Notification, notification_id)
    assert note is not None
    try:
        await send_feishu(message)
        note.ok = True
    except Exception as exc:
        note.error = str(exc)[:500]
        log.warning("推送失败：%s", exc)
    await session.commit()


async def notify_item(session: AsyncSession, item: Item, tuning: Tuning) -> int:
    if not settings.feishu_webhook_url or not worth_pushing(item, tuning):
        return 0
    rules = (await session.scalars(select(WatchRule).where(WatchRule.enabled, WatchRule.notify))).all()
    sent = 0
    for rule in rules:
        if not rule_matches(rule, item):
            continue
        if (nid := await _claim(session, item.id, rule.id, "match")) is None:
            continue
        await _deliver(session, nid, format_message(item, rule.name))
        sent += 1
        break  # 一条情报命中多个规则也只推一次
    return sent


async def remind_deadlines(session: AsyncSession, tuning: Tuning, *, within: timedelta = timedelta(days=3)) -> int:
    """关注/跟进中的商机，以及未处理但高匹配的商机，截止前 3 天提醒一次。"""
    if not settings.feishu_webhook_url:
        return 0
    now = datetime.now(UTC)
    items = (await session.scalars(
        select(Item).join(Lead).options(selectinload(Item.lead))
        .where(Lead.deadline_at.between(now, now + within),
               Lead.follow_status.in_(("watching", "following"))
               | ((Lead.follow_status == "new") & (Lead.match_score >= tuning.lead_notify_min_match)))
    )).all()
    sent = 0
    for item in items:
        if (nid := await _claim(session, item.id, None, "deadline")) is None:
            continue
        await _deliver(session, nid, format_message(item, "截止提醒"))
        sent += 1
    return sent
