"""日报 / 周报。

版块归类与选材由代码完成；模型只写导语、头条与版块点评，且只能引用给定编号（白名单）。
模型不可用时照样出刊（没有导语），不会拿假内容补位。素材少时如实变短。
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors.textutil import CN_TZ
from app.config import settings
from app.llm.client import LlmError, complete_json, load_prompt
from app.models import Digest, Item
from app.models.enums import DigestKind
from app.pipeline.llm_schemas import DailyOutput
from app.pipeline.tuning import load_tuning

log = logging.getLogger(__name__)

SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("商机速递", ("tender", "award", "project")),
    ("政策规划", ("policy", "planning")),
    ("电网与市场", ("company", "market")),
    ("技术与行业", ("tech", "industry")),
]
PER_SECTION = {DigestKind.DAILY: 8, DigestKind.WEEKLY: 12}


def daily_window(day: date) -> tuple[datetime, datetime]:
    """日报覆盖「前一天 08:00 至当天 08:00」（北京时间）。"""
    end = datetime.combine(day, time(8, 0), tzinfo=CN_TZ)
    return end - timedelta(days=1), end


def weekly_window(monday: date) -> tuple[datetime, datetime]:
    end = datetime.combine(monday, time(0, 0), tzinfo=CN_TZ)
    return end - timedelta(days=7), end


def group_sections(items: list[Item], per_section: int) -> list[tuple[str, list[Item]]]:
    out = []
    for name, channels in SECTIONS:
        picked = sorted((i for i in items if i.channel in channels), key=lambda i: -(i.score or 0))[:per_section]
        if picked:
            out.append((name, picked))
    return out


def _material_lines(sections: list[tuple[str, list[Item]]]) -> str:
    lines = []
    for name, items in sections:
        lines.append(f"## 版块：{name}")
        for i in items:
            lines.append(f"[{i.id}] {i.title_zh or i.title}（{i.source.name}，评分 {i.score:.0f}）：{i.summary or ''}")
    return "\n".join(lines)


def render_markdown(title: str, content: dict, items_by_id: dict[int, Item]) -> str:
    md = [f"# {title}", ""]
    if content.get("overview"):
        md += [f"> {content['overview']}", ""]
    if (lead := items_by_id.get(content.get("lead_id") or 0)) is not None:
        md += [f"**头条**：[{content.get('lead_title') or lead.title_zh or lead.title}]({lead.url})", ""]
    for sec in content["sections"]:
        md.append(f"## {sec['name']}")
        if sec.get("comment"):
            md.append(f"*{sec['comment']}*")
        for iid in sec["item_ids"]:
            it = items_by_id[iid]
            md.append(f"- [{it.title_zh or it.title}]({it.url}) —— {it.summary or ''}")
        md.append("")
    md.append("（本期完）")
    return "\n".join(md)


async def build_digest(session: AsyncSession, kind: DigestKind, period_start: date) -> Digest:
    existing = (await session.scalars(
        select(Digest).where(Digest.kind == kind, Digest.period_start == period_start)
    )).first()
    if kind == DigestKind.DAILY:
        start, end = daily_window(period_start)
    else:
        start, end = weekly_window(period_start)

    items = list((await session.scalars(
        select(Item).options(selectinload(Item.lead))
        .where(Item.selected, Item.is_story_lead, Item.first_seen_at >= start.astimezone(UTC),
               Item.first_seen_at < end.astimezone(UTC))
    )).all())
    sections = group_sections(items, PER_SECTION[kind])
    chosen = [i for _, sec in sections for i in sec]
    items_by_id = {i.id: i for i in chosen}

    content: dict = {
        "window": [start.isoformat(), end.isoformat()],
        "lead_id": None, "lead_title": None, "overview": None, "ai": False,
        "sections": [{"name": n, "comment": "", "item_ids": [i.id for i in sec]} for n, sec in sections],
        "stats": {
            "items": len(chosen),
            "sources": len({i.source_id for i in chosen}),
            "first_party": sum(1 for i in chosen if i.tier == "T1"),
            "leads": sum(1 for i in chosen if i.lead is not None),
        },
    }
    if chosen:
        content["lead_id"] = max(chosen, key=lambda i: i.score or 0).id
        if settings.llm_enabled:
            tuning = await load_tuning(session)
            try:
                out = await complete_json(
                    task=f"digest_{kind}",
                    model=settings.llm_model_pro,
                    system=load_prompt("daily").replace("{focus}", tuning.focus),
                    user=_material_lines(sections),
                    schema=DailyOutput,
                    max_tokens=2000,
                    temperature=0.4,
                    reasoning="low",
                )
            except LlmError as exc:
                log.warning("日报导语生成失败，照常出刊：%s", exc)
            else:
                if out.lead_id in items_by_id:  # 白名单：只接受素材内编号
                    content["lead_id"] = out.lead_id
                    content["lead_title"] = out.lead_title or None
                content["overview"] = out.overview or None
                comments = {s.name: s.comment for s in out.sections}
                for sec in content["sections"]:
                    sec["comment"] = comments.get(sec["name"], "")
                content["ai"] = True

    if existing is not None:
        digest = existing
    else:
        issue_no = (await session.scalar(select(func.count()).where(Digest.kind == kind))) or 0
        digest = Digest(kind=kind, period_start=period_start, issue_no=issue_no + 1)
        session.add(digest)
    label = "日报" if kind == DigestKind.DAILY else "周报"
    span = (f"{period_start.year}年{period_start.month}月{period_start.day}日" if kind == DigestKind.DAILY
            else f"{start:%m.%d}–{(end - timedelta(days=1)):%m.%d}")
    digest.title = f"电力基建情报{label} · 第{digest.issue_no}期 · {span}"
    digest.period_end = (end - timedelta(seconds=1)).date()
    digest.content = content
    digest.markdown = render_markdown(digest.title, content, items_by_id)
    await session.commit()
    return digest
