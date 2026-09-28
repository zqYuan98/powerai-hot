"""API 契约。前端类型由 OpenAPI 自动生成，这里是唯一来源。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BizLine, Channel, FollowStatus, Stage


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


class Ok(Out):
    ok: bool = True
    detail: str | None = None
