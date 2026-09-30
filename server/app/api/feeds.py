"""RSS 2.0 订阅与 llms.txt。挂在站点根路径（Caddy 把 /feed.xml、/feed/*、/llms.txt 分流到这里）。"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Annotated
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import digests, items, knowledge, leads
from app.config import settings
from app.db import get_session
from app.models import Digest
from app.models.enums import CHANNEL_LABELS, DOMAIN_LABELS, KTYPE_LABELS, Channel, DigestKind
from app.schemas.public import V1Item, V1Knowledge, site_url, v1_item, v1_knowledge

router = APIRouter(include_in_schema=False)
Session = Annotated[AsyncSession, Depends(get_session)]
SITE_NAME = "电力基建情报站"
STAGE_TEXT = {"planning": "规划", "approval": "核准", "feasibility": "可研", "tendering": "招标中",
              "awarded": "已中标", "construction": "在建", "operation": "投运"}
FEED_HEADERS = {"Cache-Control": "public, max-age=300"}


def _entry(item: V1Item) -> str:
    parts = []
    if lead := item.lead:
        facts = [STAGE_TEXT.get(lead.stage, ""),
                 f"{lead.amount_wan:g} 万元" if lead.amount_wan is not None else "",
                 f"{lead.voltage_kv} kV" if lead.voltage_kv else "",
                 f"业主：{lead.owner}" if lead.owner else "",
                 f"截止：{lead.deadline_at.astimezone(settings.tz):%Y-%m-%d %H:%M}" if lead.deadline_at else ""]
        if facts := [f for f in facts if f]:
            parts.append(f"<p><b>{escape(' · '.join(facts))}</b></p>")
    if item.summary:
        parts.append(f"<p>{escape(item.summary)}</p>")
    if item.reason:
        parts.append(f"<p>推荐理由：{escape(item.reason)}</p>")
    parts.append(f'<p>{escape(item.source)} · <a href="{escape(item.source_url)}">原文</a></p>')
    return (
        "<item>"
        f"<title>{escape(item.title)}</title>"
        f"<link>{escape(item.url)}</link>"
        f'<guid isPermaLink="true">{escape(item.url)}</guid>'
        f"<pubDate>{format_datetime(item.first_seen_at)}</pubDate>"
        f"<category>{escape(CHANNEL_LABELS.get(item.channel, item.channel))}</category>"
        f"<description>{escape(''.join(parts))}</description>"
        "</item>"
    )


def _rss(title: str, path: str, description: str, entries: Iterable[str]) -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{escape(title)}</title>"
        f"<link>{escape(site_url('/'))}</link>"
        f'<atom:link href="{escape(site_url(path))}" rel="self" type="application/rss+xml"/>'
        f"<description>{escape(description)}</description>"
        "<language>zh-CN</language>"
        f"<lastBuildDate>{format_datetime(datetime.now(UTC))}</lastBuildDate>"
        f"{''.join(entries)}"
        "</channel></rss>"
    )
    return Response(body, media_type="application/rss+xml; charset=utf-8", headers=FEED_HEADERS)


@router.get("/feed.xml")
async def feed_selected(session: Session) -> Response:
    page = await items.list_items(session, admin=False, view="selected", channel=None, province=None,
                                  source_id=None, q=None, since=None, cursor=None, limit=50)
    return _rss(f"{SITE_NAME} · 精选", "/feed.xml", "AI 精读筛出的电力基建情报，最新 50 条",
                (_entry(v1_item(c)) for c in page.items))


@router.get("/feed/all.xml")
async def feed_all(session: Session) -> Response:
    page = await items.list_items(session, admin=False, view="all", channel=None, province=None, source_id=None,
                                  q=None, since=datetime.now(UTC) - timedelta(days=7), cursor=None, limit=100)
    return _rss(f"{SITE_NAME} · 全部", "/feed/all.xml", "最近 7 天完成精读的全部动态，最多 100 条",
                (_entry(v1_item(c)) for c in page.items))


@router.get("/feed/leads.xml")
async def feed_leads(session: Session) -> Response:
    page = await leads.list_leads(session, admin=False, stage=None, province=None, biz_line=None, follow=None,
                                  min_amount_wan=None, min_voltage_kv=None, open_only=False, q=None,
                                  sort="recent", offset=0, limit=50)
    return _rss(f"{SITE_NAME} · 商机", "/feed/leads.xml", "招标、中标、项目与规划中抽取的结构化商机，最新 50 条",
                (_entry(v1_item(r.item)) for r in page.items))


@router.get("/feed/channel/{channel}.xml")
async def feed_channel(session: Session, channel: Channel) -> Response:
    page = await items.list_items(session, admin=False, view="selected", channel=channel, province=None,
                                  source_id=None, q=None, since=None, cursor=None, limit=50)
    label = CHANNEL_LABELS[channel]
    return _rss(f"{SITE_NAME} · {label}", f"/feed/channel/{channel.value}.xml", f"「{label}」频道的精选，最新 50 条",
                (_entry(v1_item(c)) for c in page.items))


def _knowledge_entry(k: V1Knowledge) -> str:
    parts = [f"<p>{escape(k.summary)}</p>"] if k.summary else []
    if k.key_points:
        parts.append("<ul>" + "".join(f"<li>{escape(p)}</li>" for p in k.key_points) + "</ul>")
    if k.standards:
        parts.append(f"<p>涉及标准：{escape('、'.join(k.standards))}</p>")
    parts.append(f'<p>{escape(k.account or "")} · <a href="{escape(k.source_url)}">原文</a></p>')
    return (
        f"<item><title>{escape(k.title)}</title><link>{escape(k.url)}</link>"
        f'<guid isPermaLink="true">{escape(k.url)}</guid>'
        f"<pubDate>{format_datetime(k.published_at or datetime.now(UTC))}</pubDate>"
        f"<category>{escape(DOMAIN_LABELS[k.domain])}</category><category>{escape(KTYPE_LABELS[k.ktype])}</category>"
        f"<description>{escape(''.join(parts))}</description></item>"
    )


@router.get("/feed/knowledge.xml")
async def feed_knowledge(session: Session) -> Response:
    page = await knowledge.list_knowledge(session, admin=False, domain=None, ktype=None, q=None, featured=False,
                                          sort="recent", status=None, offset=0, limit=50)
    return _rss(f"{SITE_NAME} · 知识", "/feed/knowledge.xml", "电力基建知识库最新收录的 50 篇知识卡片",
                (_knowledge_entry(v1_knowledge(k)) for k in page.items))


@router.get("/feed/daily.xml")
async def feed_daily(session: Session) -> Response:
    rows = (await session.scalars(
        select(Digest).where(Digest.kind == DigestKind.DAILY).order_by(Digest.period_start.desc()).limit(30)
    )).all()
    entries = []
    for d in rows:
        detail = await digests.digest_detail(session, d)
        url = site_url(f"/daily/daily/{d.period_start}")
        html = [f"<p>{escape(detail.overview)}</p>"] if detail.overview else []
        for sec in detail.sections:
            links = "".join(f'<li><a href="{escape(site_url(f"/items/{c.id}"))}">{escape(c.title_zh or c.title)}</a>'
                            f"</li>" for c in sec.items)
            html.append(f"<h3>{escape(sec.name)}</h3><ul>{links}</ul>")
        entries.append(
            f"<item><title>{escape(d.title)}</title><link>{escape(url)}</link>"
            f'<guid isPermaLink="true">{escape(url)}</guid>'
            f"<pubDate>{format_datetime(d.created_at)}</pubDate>"
            f"<description>{escape(''.join(html))}</description></item>"
        )
    return _rss(f"{SITE_NAME} · 日报", "/feed/daily.xml", "每天 08:00（北京时间）发布，保留最近 30 期", entries)


LLMS_TXT = """# 电力基建情报站

> 面向电力基建（输变电工程、智能运检 / AI 视觉）的中文情报站。自动采集政府、电网公司、招标平台与行业媒体，
> 由大模型精读打分、抽取商机字段并回原文核验，把同一件事的多家报道归并成事件，每天 08:00（北京时间）出日报。

所有内容匿名只读、无需 token。标题、摘要、推荐理由由模型根据原文生成；金额、截止时间、资质等关键信息请以原文为准。

## 给 Agent 的接入方式

- MCP Server（Streamable HTTP，无需鉴权）：{base}/api/mcp
  工具：latest（最近精选 / 全部）、search（搜索）、leads（结构化商机）、
  hot（热点事件）、story（事件时间线）、daily（日报）、knowledge（行业知识库）
- REST API v1：{base}/api/v1/items、/api/v1/leads、/api/v1/search、/api/v1/hot、
  /api/v1/stories/{{id}}、/api/v1/dailies/latest、/api/v1/knowledge
  完整定义：{base}/api/v1/openapi.json
- RSS 2.0：{base}/feed.xml（精选）、{base}/feed/leads.xml（商机）、
  {base}/feed/daily.xml（日报）、{base}/feed/all.xml（最近 7 天全部）、{base}/feed/knowledge.xml（知识库）
  分频道：{base}/feed/channel/{{tender|award|project|planning|policy|market|company|tech|industry}}.xml

## 页面

- 精选：{base}/
- 商机：{base}/leads
- 热点：{base}/hot
- 日报：{base}/daily
- 知识库：{base}/knowledge
- 接入说明：{base}/agent
- 关于：{base}/about
"""


@router.get("/llms.txt")
async def llms_txt() -> Response:
    return Response(LLMS_TXT.format(base=site_url("")), media_type="text/plain; charset=utf-8",
                    headers=FEED_HEADERS)
