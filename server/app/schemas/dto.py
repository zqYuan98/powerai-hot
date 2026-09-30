"""API 契约。前端类型由 OpenAPI 自动生成，这里是唯一来源。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BizLine, Channel, FollowStatus, KnowledgeDomain, KnowledgeType, Stage


class Out(BaseModel):
    """响应模型：按序列化模式生成 schema，带默认值的字段在前端类型里也是必有的。"""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ORM(Out):
    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)


class SourceBrief(ORM):
    id: int
    key: str
    name: str
    tier: str


class LeadOut(ORM):
    project_name: str | None
    owner: str | None
    province: str | None
    voltage_kv: int | None
    amount_wan: Decimal | None
    stage: Stage
    bid_no: str | None
    deadline_at: datetime | None
    qualification: str | None
    winner: str | None
    biz_line: BizLine
    match_score: int
    dropped_fields: list[str]
    follow_status: FollowStatus
    follow_note: str | None
    remind_at: datetime | None


class ItemCard(ORM):
    id: int
    title: str
    title_zh: str | None
    url: str
    source: SourceBrief
    tier: str
    channel: Channel
    province: str | None
    summary: str | None
    reason: str | None
    action: str | None
    tags: list[str]
    score: float | None
    selected: bool
    published_at: datetime | None
    first_seen_at: datetime
    story_id: int | None
    also_reported: int = 0  # 另有 N 家信源报道
    starred: bool = False
    read: bool = False
    lead: LeadOut | None = None


class Dims(Out):
    relevance: int | None
    opportunity: int | None
    certainty: int | None
    timeliness: int | None
    impact: int | None


class StoryBrief(ORM):
    id: int
    title: str
    item_count: int
    source_count: int
    heat: float
    status: str


class ItemDetail(ItemCard):
    content_html: str | None
    content_text: str | None
    note: str | None
    status: str
    status_reason: str | None
    dims: Dims
    story: StoryBrief | None = None
    related: list[ItemCard] = Field(default_factory=list)


class Page[T](Out):
    items: list[T]
    next_cursor: str | None = None


class ItemPatch(BaseModel):
    starred: bool | None = None
    read: bool | None = None
    note: str | None = Field(default=None, max_length=5000)


class LeadPatch(BaseModel):
    follow_status: FollowStatus | None = None
    follow_note: str | None = Field(default=None, max_length=5000)
    remind_at: datetime | None = None


class LeadRow(Out):
    item: ItemCard
    lead: LeadOut


class LeadPage(Out):
    items: list[LeadRow]
    total: int


class HotStory(Out):
    rank: int
    story: StoryBrief
    lead_item: ItemCard
    first_seen_at: datetime
    last_seen_at: datetime
    is_new: bool  # 6 小时内首报


class StoryDetail(Out):
    story: StoryBrief
    digest: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    timeline: list[ItemCard]


class DigestBrief(ORM):
    id: int
    kind: Literal["daily", "weekly"]
    period_start: date
    period_end: date
    issue_no: int
    title: str
    lead_title: str | None = None
    item_count: int = 0


class DigestSection(Out):
    name: str
    comment: str
    items: list[ItemCard]


class DigestDetail(DigestBrief):
    overview: str | None
    lead: ItemCard | None
    sections: list[DigestSection]
    stats: dict[str, int]
    markdown: str


class ChannelCount(Out):
    channel: Channel
    label: str
    today: int


class Meta(Out):
    channels: list[ChannelCount]
    last_collect_at: datetime | None
    sources_enabled: int
    llm_enabled: bool
    embedding_enabled: bool
    push_enabled: bool
    auth_required: bool


class SourceOut(ORM):
    id: int
    key: str
    name: str
    kind: str
    url: str
    tier: str
    category: str
    enabled: bool
    interval_min: int
    notes: str | None
    last_run_at: datetime | None
    last_ok_at: datetime | None
    last_error: str | None
    fail_streak: int
    runs_24h: int = 0
    ok_24h: int = 0
    new_7d: int = 0
    selected_7d: int = 0


class SourcePatch(BaseModel):
    enabled: bool | None = None
    interval_min: int | None = Field(default=None, ge=10, le=10080)


class SourceRunOut(ORM):
    id: int
    started_at: datetime
    duration_ms: int
    transport_status: str
    parse_status: str
    http_status: int | None
    fetched: int
    new_count: int
    error: str | None


class WatchRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    keywords: list[str] = Field(default_factory=list)
    provinces: list[str] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    min_amount_wan: Decimal | None = None
    min_voltage_kv: int | None = None
    notify: bool = True
    enabled: bool = True


class WatchRuleOut(WatchRuleIn, ORM):
    id: int


class UsageDay(Out):
    day: date
    task: str
    calls: int
    failures: int
    prompt_tokens: int
    completion_tokens: int
    cost_yuan: float


class UsageOut(Out):
    days: list[UsageDay]
    recent_errors: list[dict[str, Any]]


class JobOut(ORM):
    id: int
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    error: str | None
    result: dict[str, Any] | None
    created_at: datetime
    finished_at: datetime | None


class PipelineStats(Out):
    items_24h: int
    analyzed_24h: int
    selected_24h: int
    screened_out_24h: int
    failed_pending: int
    queued_jobs: int
    running_jobs: int


class LoginIn(BaseModel):
    password: str


class Viewer(Out):
    admin: bool
    auth_required: bool


# ---------- 反馈 ----------

class FeedbackIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(min_length=2, max_length=2000)
    contact: str | None = Field(default=None, max_length=200)
    page_url: str | None = Field(default=None, max_length=500)


class FeedbackAck(Out):
    id: int


class FeedbackOut(ORM):
    id: int
    content: str
    contact: str | None
    page_url: str | None
    ip: str | None
    user_agent: str | None
    status: Literal["new", "done"]
    created_at: datetime


class FeedbackPatch(BaseModel):
    status: Literal["new", "done"]


class Ok(Out):
    ok: bool = True
    detail: str | None = None


# ---------- 精选校准 ----------

GoldDecision = Literal["select", "reject", "either"]


class GoldCase(Out):
    """待标注条目：只给原文，不给分数、AI 摘要和精选结论，避免标注被系统判断带偏。"""

    item_id: int
    title: str
    url: str
    source_name: str
    tier: str
    published_at: datetime | None
    first_seen_at: datetime
    body: str | None
    decision: GoldDecision | None = None
    note: str | None = None


class GoldLabelIn(BaseModel):
    decision: GoldDecision
    note: str | None = Field(default=None, max_length=500)


class GoldRecent(Out):
    item_id: int
    title: str
    decision: GoldDecision
    labeled_at: datetime


class GoldStats(Out):
    total: int
    target: int
    decision: dict[str, int]
    stratum: dict[str, int]
    split: dict[str, int]
    recent: list[GoldRecent]


class EvalRunIn(BaseModel):
    mode: Literal["stored", "rerun"] = "stored"
    split: Literal["development", "holdout", "all"] = "development"
    label: str | None = Field(default=None, max_length=100)


class EvalRunBrief(ORM):
    id: int
    label: str
    mode: str
    split: str
    status: str
    error: str | None
    metrics: dict[str, Any]
    cost_yuan: float
    created_at: datetime
    finished_at: datetime | None


class EvalRunDetail(EvalRunBrief):
    params: dict[str, Any]
    sweep: list[dict[str, Any]]
    errors: list[dict[str, Any]]


# ---------- 知识库 ----------

class KnowledgeCard(Out):
    id: int
    title: str
    original_title: str
    url: str
    account: str | None
    published_at: datetime | None
    created_at: datetime
    domain: KnowledgeDomain
    ktype: KnowledgeType
    tags: list[str]
    summary: str | None
    key_points: list[str]
    scenarios: str | None
    solution_use: str | None
    standards: list[str]
    score: float | None
    featured: bool
    status: Literal["new", "analyzed", "rejected", "duplicate", "hidden", "failed"]
    status_reason: str | None = None  # 未通过/失败的原因，仅管理员


class KnowledgeDims(Out):
    depth: int | None
    practical: int | None
    accuracy: int | None
    originality: int | None


class KnowledgeDetail(KnowledgeCard):
    dims: KnowledgeDims
    related: list[KnowledgeCard]
    # 以下仅管理员可见（访客为空）
    content_text: str | None
    note: str | None
    duplicate_of: int | None


class KnowledgePage(Out):
    items: list[KnowledgeCard]
    total: int


class FacetCount(Out):
    key: str
    label: str
    count: int


class KnowledgeFacets(Out):
    total: int
    domains: list[FacetCount]
    types: list[FacetCount]
    status: dict[str, int]  # 各状态数量，仅管理员


class KnowledgeSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(min_length=8, max_length=1000)
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=50000, description="抓不到正文时直接粘贴")
    note: str | None = Field(default=None, max_length=2000)


class KnowledgeSubmitAck(Out):
    id: int
    existed: bool
    status: str


class KnowledgePatch(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    hidden: bool | None = None
    domain: KnowledgeDomain | None = None
    ktype: KnowledgeType | None = None
