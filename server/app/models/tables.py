"""全部表定义。schema 的唯一来源是 Alembic 迁移；这里与迁移保持一致。

时间一律 timestamptz（UTC 存储）；枚举存英文代码（见 enums.py）。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBEDDING_DIM = 1024

TS = DateTime(timezone=True)
NOW = text("now()")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    url: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(8), default="T2")
    category: Mapped[str] = mapped_column(String(16), default="industry")  # 默认频道
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_min: Mapped[int] = mapped_column(Integer, default=120)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    last_run_at: Mapped[datetime | None] = mapped_column(TS)
    last_ok_at: Mapped[datetime | None] = mapped_column(TS)
    last_error: Mapped[str | None] = mapped_column(Text)
    fail_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class SourceRun(Base):
    __tablename__ = "source_runs"
    __table_args__ = (Index("ix_source_runs_source_started", "source_id", text("started_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    transport_status: Mapped[str] = mapped_column(String(16))
    parse_status: Mapped[str] = mapped_column(String(16))
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Story(Base):
    """事件/项目归并：同一招标、同一项目、同一新闻事件的多条报道。"""

    __tablename__ = "stories"
    __table_args__ = (Index("ix_stories_heat", text("heat DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    title: Mapped[str] = mapped_column(Text)
    digest: Mapped[str | None] = mapped_column(Text)  # AI 综述（含尚未披露的信息）
    status: Mapped[str] = mapped_column(String(16), default="active")
    first_seen_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    heat: Mapped[float] = mapped_column(Float, default=0.0)
    digest_item_count: Mapped[int] = mapped_column(Integer, default=0)  # 生成综述时的条目数


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        # 信息流按「发现时间」倒序 + 仅主稿；部分索引覆盖精选流与频道流
        Index("ix_items_feed", text("first_seen_at DESC"), text("id DESC"),
              postgresql_where=text("status = 'analyzed' AND is_story_lead")),
        Index("ix_items_feed_selected", text("first_seen_at DESC"), text("id DESC"),
              postgresql_where=text("selected AND is_story_lead")),
        Index("ix_items_channel_feed", "channel", text("first_seen_at DESC"), text("id DESC"),
              postgresql_where=text("status = 'analyzed' AND is_story_lead")),
        Index("ix_items_status", "status"),
        Index("ix_items_story", "story_id"),
        Index("ix_items_source", "source_id"),
        Index("ix_items_starred", "starred_at", postgresql_where=text("starred_at IS NOT NULL")),
        Index(
            "ix_items_title_trgm",
            text("(coalesce(title_zh, '') || ' ' || title) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "ix_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    tier: Mapped[str] = mapped_column(String(8))
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    title_zh: Mapped[str | None] = mapped_column(Text)  # 模型改写的中文短标题
    content_text: Mapped[str | None] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)  # 已消毒
    published_at: Mapped[datetime | None] = mapped_column(TS)
    first_seen_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)

    status: Mapped[str] = mapped_column(String(16), default="new")
    status_reason: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    analyzed_at: Mapped[datetime | None] = mapped_column(TS)

    channel: Mapped[str] = mapped_column(String(16), default="industry")
    province: Mapped[str | None] = mapped_column(String(16))
    summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)   # 推荐理由
    action: Mapped[str | None] = mapped_column(Text)   # 建议动作
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    event_key: Mapped[str | None] = mapped_column(String(200))

    # 五维 0-10，独立列便于排序与调参回放
    d_relevance: Mapped[int | None] = mapped_column(SmallInteger)
    d_opportunity: Mapped[int | None] = mapped_column(SmallInteger)
    d_certainty: Mapped[int | None] = mapped_column(SmallInteger)
    d_timeliness: Mapped[int | None] = mapped_column(SmallInteger)
    d_impact: Mapped[int | None] = mapped_column(SmallInteger)
    score: Mapped[float | None] = mapped_column(Float)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)

    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"))
    is_story_lead: Mapped[bool] = mapped_column(Boolean, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    starred_at: Mapped[datetime | None] = mapped_column(TS)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    note: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(lazy="joined", innerjoin=True)
    lead: Mapped[Lead | None] = relationship(back_populates="item", lazy="selectin", uselist=False)


class Lead(Base):
    """商机结构化字段，与 items 1:1。所有抽取字段均经过 grounding 校验。"""

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_deadline", "deadline_at"),
        Index("ix_leads_follow", "follow_status"),
        Index("ix_leads_bid_no", "bid_no"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    project_name: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(Text)  # 业主/招标人
    province: Mapped[str | None] = mapped_column(String(16))
    voltage_kv: Mapped[int | None] = mapped_column(Integer)
    amount_wan: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # 金额（万元）
    stage: Mapped[str] = mapped_column(String(16), default="unknown")
    bid_no: Mapped[str | None] = mapped_column(String(100))
    deadline_at: Mapped[datetime | None] = mapped_column(TS)
    qualification: Mapped[str | None] = mapped_column(Text)
    winner: Mapped[str | None] = mapped_column(Text)
    biz_line: Mapped[str] = mapped_column(String(16), default="other")
    match_score: Mapped[int] = mapped_column(SmallInteger, default=0)  # 0-100 与业务匹配度
    dropped_fields: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)  # grounding 丢弃的字段

    follow_status: Mapped[str] = mapped_column(String(16), default="new")
    follow_note: Mapped[str | None] = mapped_column(Text)
    remind_at: Mapped[datetime | None] = mapped_column(TS)
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=NOW, onupdate=NOW)

    item: Mapped[Item] = relationship(back_populates="lead")


class WatchRule(Base):
    __tablename__ = "watch_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    provinces: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    min_amount_wan: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    min_voltage_kv: Mapped[int | None] = mapped_column(Integer)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class Notification(Base):
    """推送记录，唯一约束保证同一条目同一规则同一类型只推一次。"""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("item_id", "rule_id", "kind", postgresql_nulls_not_distinct=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("watch_rules.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))  # match | deadline
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = (UniqueConstraint("kind", "period_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    issue_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class Job(Base):
    """持久任务队列（FOR UPDATE SKIP LOCKED 认领）。"""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_claim", "status", "priority", "run_after", postgresql_where=text("status = 'queued'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=3)
    run_after: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    locked_by: Mapped[str | None] = mapped_column(String(64))
    heartbeat_at: Mapped[datetime | None] = mapped_column(TS)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


# 活跃任务的去重：同一 dedupe_key 只允许一个 queued/running
Index(
    "ux_jobs_active_dedupe",
    Job.dedupe_key,
    unique=True,
    postgresql_where=text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
)


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (Index("ix_llm_calls_created", text("created_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_yuan: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)


class GoldLabel(Base):
    """人工标注的「该选/不该选」，用于校准精选（见 pipeline/evaluate.py）。有标注的条目不会被清理正文。"""

    __tablename__ = "gold_labels"

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    decision: Mapped[str] = mapped_column(String(8))    # select | reject | either
    split: Mapped[str] = mapped_column(String(12))      # development | holdout
    stratum: Mapped[str] = mapped_column(String(12))    # 抽样时所在的层：selected | near | low | screened
    note: Mapped[str | None] = mapped_column(Text)
    labeled_at: Mapped[datetime] = mapped_column(TS, server_default=NOW, onupdate=NOW)


class EvalRun(Base):
    """一次精选评测：当时的配置、总体指标、门槛扫描与逐条结果。"""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(8))        # stored 用库里已有判断 | rerun 用当前提示词重跑
    split: Mapped[str] = mapped_column(String(12))      # development | holdout | all
    status: Mapped[str] = mapped_column(String(8), default="running")  # running | done | failed
    error: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sweep: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cost_yuan: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=NOW)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=NOW, onupdate=NOW)
