"""对外开放的只读数据契约：REST API v1、MCP、RSS 共用。

与站内接口（dto.py）解耦：站内可以随改随用，这里只增字段不改语义。
不含任何个人数据（收藏、笔记、跟进状态）；链接一律是绝对地址（PUBLIC_BASE_URL）。
"""
from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.config import settings
from app.models.enums import BizLine, Channel, KnowledgeDomain, KnowledgeType, Stage
from app.schemas.dto import DigestBrief, DigestDetail, HotStory, ItemCard, KnowledgeCard, LeadOut, Out, StoryDetail


def site_url(path: str) -> str:
    return settings.public_base_url.rstrip("/") + path


class V1Lead(Out):
    project_name: str | None
    owner: str | None = Field(description="业主 / 招标人")
    province: str | None
    voltage_kv: int | None
    amount_wan: float | None = Field(description="金额（万元）")
    stage: Stage
    bid_no: str | None = Field(description="招标 / 项目编号")
    deadline_at: datetime | None = Field(description="投标截止时间")
    qualification: str | None
    winner: str | None = Field(description="中标人（中标公示才有）")
    biz_line: BizLine
    match_score: int = Field(description="与站点业务画像的匹配度 0–100")


class V1Item(Out):
    id: int
    title: str = Field(description="中文短标题（模型根据原文改写）")
    original_title: str
    url: str = Field(description="站内阅读页")
    source_url: str = Field(description="原文链接")
    source: str
    tier: str = Field(description="信源档位：T1 官方一手 / T1_5 专业媒体 / T2 综合媒体")
    channel: Channel
    province: str | None
    summary: str | None
    reason: str | None = Field(description="推荐理由")
    action: str | None = Field(description="建议动作")
    tags: list[str]
    score: float | None = Field(description="AI 评分 0–100")
    selected: bool
    published_at: datetime | None
    first_seen_at: datetime
    story_id: int | None
    also_reported: int = Field(description="另有几家信源报道了同一件事")
    lead: V1Lead | None


class V1ItemPage(Out):
    items: list[V1Item]
    next_cursor: str | None = Field(description="下一页游标；为空表示没有更多")


class V1LeadPage(Out):
    items: list[V1Item]
    total: int


class V1HotStory(Out):
    rank: int
    story_id: int
    title: str
    url: str
    heat: float
    source_count: int
    item_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    is_new: bool = Field(description="6 小时内首次出现")
    lead_item: V1Item


class V1Story(Out):
    id: int
    title: str
    url: str
    digest: str | None = Field(description="AI 综述")
    source_count: int
    item_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    timeline: list[V1Item] = Field(description="按时间正序，最多最近 50 条")


class V1DigestBrief(Out):
    kind: Literal["daily", "weekly"]
    date: dt.date = Field(description="期号日期（日报为当天 08:00 截止的那一天）")
    period_end: dt.date
    issue_no: int
    title: str
    lead_title: str | None
    item_count: int
    url: str


class V1DigestSection(Out):
    name: str
    comment: str
    items: list[V1Item]


class V1Digest(V1DigestBrief):
    overview: str | None
    sections: list[V1DigestSection]
    markdown: str


class V1Knowledge(Out):
    id: int
    title: str = Field(description="中文短标题（模型改写，去掉标题党）")
    original_title: str
    url: str = Field(description="站内知识卡片页")
    source_url: str = Field(description="原文链接")
    account: str | None = Field(description="公众号 / 作者 / 站点")
    published_at: datetime | None
    domain: KnowledgeDomain
    ktype: KnowledgeType
    tags: list[str]
    summary: str | None
    key_points: list[str] = Field(description="3–5 条核心要点，仅来自原文")
    scenarios: str | None = Field(description="适用场景")
    solution_use: str | None = Field(description="可用于哪类方案的哪一部分")
    standards: list[str] = Field(description="原文出现的标准规范编号（已回原文核验）")
    score: float | None = Field(description="质量分 0–100（深度、实用性、准确性、原创性）")
    featured: bool


class V1KnowledgePage(Out):
    items: list[V1Knowledge]
    total: int


def v1_knowledge(k: KnowledgeCard) -> V1Knowledge:
    return V1Knowledge(
        id=k.id, title=k.title, original_title=k.original_title, url=site_url(f"/knowledge/{k.id}"),
        source_url=k.url, account=k.account, published_at=k.published_at, domain=k.domain, ktype=k.ktype,
        tags=k.tags, summary=k.summary, key_points=k.key_points, scenarios=k.scenarios,
        solution_use=k.solution_use, standards=k.standards, score=k.score, featured=k.featured,
    )


def v1_lead(lead: LeadOut) -> V1Lead:
    return V1Lead(
        project_name=lead.project_name, owner=lead.owner, province=lead.province, voltage_kv=lead.voltage_kv,
        amount_wan=float(lead.amount_wan) if lead.amount_wan is not None else None, stage=lead.stage,
        bid_no=lead.bid_no, deadline_at=lead.deadline_at, qualification=lead.qualification, winner=lead.winner,
        biz_line=lead.biz_line, match_score=lead.match_score,
    )


def v1_item(card: ItemCard) -> V1Item:
    return V1Item(
        id=card.id, title=card.title_zh or card.title, original_title=card.title, url=site_url(f"/items/{card.id}"),
        source_url=card.url, source=card.source.name, tier=card.tier, channel=card.channel, province=card.province,
        summary=card.summary, reason=card.reason, action=card.action, tags=card.tags, score=card.score,
        selected=card.selected, published_at=card.published_at, first_seen_at=card.first_seen_at,
        story_id=card.story_id, also_reported=card.also_reported, lead=v1_lead(card.lead) if card.lead else None,
    )


def v1_hot(h: HotStory) -> V1HotStory:
    return V1HotStory(
        rank=h.rank, story_id=h.story.id, title=h.story.title, url=site_url(f"/stories/{h.story.id}"),
        heat=h.story.heat, source_count=h.story.source_count, item_count=h.story.item_count,
        first_seen_at=h.first_seen_at, last_seen_at=h.last_seen_at, is_new=h.is_new, lead_item=v1_item(h.lead_item),
    )


def v1_story(s: StoryDetail) -> V1Story:
    return V1Story(
        id=s.story.id, title=s.story.title, url=site_url(f"/stories/{s.story.id}"), digest=s.digest,
        source_count=s.story.source_count, item_count=s.story.item_count, first_seen_at=s.first_seen_at,
        last_seen_at=s.last_seen_at, timeline=[v1_item(c) for c in s.timeline[-50:]],
    )


def v1_digest_brief(d: DigestBrief) -> V1DigestBrief:
    return V1DigestBrief(
        kind=d.kind, date=d.period_start, period_end=d.period_end, issue_no=d.issue_no, title=d.title,
        lead_title=d.lead_title, item_count=d.item_count, url=site_url(f"/daily/{d.kind}/{d.period_start}"),
    )


def v1_digest(d: DigestDetail) -> V1Digest:
    return V1Digest(
        **v1_digest_brief(d).model_dump(), overview=d.overview, markdown=d.markdown,
        sections=[V1DigestSection(name=s.name, comment=s.comment, items=[v1_item(c) for c in s.items])
                  for s in d.sections],
    )
