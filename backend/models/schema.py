"""SQLAlchemy data models — mirrors the core tables in the design doc."""
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import (
    ARRAY,
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from models.database import Base

# 字符串数组：PostgreSQL 用原生 ARRAY，SQLite（本地零配置）回退到 JSON。
STR_ARRAY = ARRAY(String).with_variant(JSON(), "sqlite")


def normalize_source_name(value: str | None) -> str:
    """Return a stable key for source-name uniqueness checks."""
    return " ".join((value or "").split()).casefold()


def normalize_source_url(value: str | None) -> str | None:
    """Return a stable URL key, or ``None`` for legacy blank URLs."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        # Administrator website entries historically accepted opaque URLs;
        # retain a deterministic key without turning malformed input into a
        # server error. Employee submissions validate before normalization.
        return value.casefold()
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path.rstrip("/") or "/",
            parsed.query,
            "",
        )
    )


def normalize_thread_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    name_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    url_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    type: Mapped[str] = mapped_column(String(20), default="网站")  # 网站 | 公众号 | RSS
    status: Mapped[str] = mapped_column(String(20), default="待审核")  # 待审核 | 已采纳 | 未通过
    submitted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier: Mapped[str] = mapped_column(String(8), default="T2")  # T1 | T1.5 | T2
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ok | error
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawl_interval_hours: Mapped[int] = mapped_column(Integer, default=1)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="source")
    source_runs: Mapped[list["SourceRun"]] = relationship(back_populates="source")


Index("uq_sources_name_key", Source.name_key, unique=True)
Index("uq_sources_url_key", Source.url_key, unique=True)


class ResearchThread(Base):
    __tablename__ = "research_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(STR_ARRAY, default=list)
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @validates("name")
    def _set_name_key(self, _key: str, value: str) -> str:
        self.name_key = normalize_thread_name(value)
        return value


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(400))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)  # 消毒后的富文本正文（站内读全文）
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI-generated
    tags: Mapped[list[str]] = mapped_column(STR_ARRAY, default=list)
    channel: Mapped[str] = mapped_column(String(40), default="行业动态")
    org: Mapped[str | None] = mapped_column(String(80), nullable=True)  # 国家电网/南方电网...
    hot: Mapped[bool] = mapped_column(default=False)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 招标截止
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    url_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_label: Mapped[str | None] = mapped_column(String(40), nullable=True)  # "2 小时前"
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(16), default="processed", server_default="processed")
    scored_by: Mapped[str] = mapped_column(String(20), default="unscored", server_default="unscored")
    crawled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    # AI 精选机制：相关度分(0-100) / 推荐理由 / 是否进入「精选」
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    recommend_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    curated: Mapped[bool] = mapped_column(default=False)
    # 双轴（2026-07-25）：cross_score = √(ai_relevance × power_relevance)，
    # axis ∈ 交叉/AI/行业/弱，见 analyzer/scoring.py
    cross_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    axis: Mapped[str] = mapped_column(String(8), default="弱", server_default="弱")
    # 个人研究扩展（2026-07-03 设计）
    kind: Mapped[str] = mapped_column(String(8), default="资讯")  # 资讯 | 论文 | 案例
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 论文: authors/arxiv_id/pdf_url/...
    dim_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 六维原始分（DIM_KEYS）
    tier: Mapped[str] = mapped_column(String(8), default="T2")  # 信源分级快照
    scored: Mapped[bool] = mapped_column(default=False)  # 预筛通过且完成评分
    noise_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 预筛打回原因（噪音视图）
    # 事件聚类（Phase 2）
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    is_cluster_main: Mapped[bool] = mapped_column(default=True)
    primary_thread_id: Mapped[int | None] = mapped_column(ForeignKey("research_threads.id"), nullable=True)
    thread_affinity: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    source: Mapped["Source"] = relationship(back_populates="articles")


Index("ix_articles_feed_latest", Article.channel, Article.scored, Article.crawled_at, Article.id)
Index(
    "ix_articles_feed_curated_score",
    Article.channel, Article.curated, Article.scored,
    Article.relevance_score, Article.crawled_at, Article.id,
)
Index("ix_articles_published_at", Article.published_at)
Index("ix_articles_processing_status", Article.processing_status, Article.scored_by)
Index("ix_articles_primary_thread", Article.primary_thread_id, Article.scored, Article.crawled_at)


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        UniqueConstraint("run_key", name="uq_job_runs_run_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_key: Mapped[str] = mapped_column(String(120), nullable=False)
    job_name: Mapped[str] = mapped_column(String(60), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", server_default="running")
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    model_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fallback_model_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rule_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    source_runs: Mapped[list["SourceRun"]] = relationship(back_populates="job_run")


Index("ix_job_runs_status_started", JobRun.status, JobRun.started_at)


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport_status: Mapped[str] = mapped_column(String(20), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    newest_item_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    job_run: Mapped["JobRun"] = relationship(back_populates="source_runs")
    source: Mapped["Source"] = relationship(back_populates="source_runs")


Index("ix_source_runs_job_source", SourceRun.job_run_id, SourceRun.source_id)
Index("ix_source_runs_status", SourceRun.transport_status, SourceRun.parse_status)


class PersistentJob(Base):
    __tablename__ = "persistent_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_persistent_jobs_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


Index(
    "ix_persistent_jobs_claim",
    PersistentJob.status,
    PersistentJob.available_at,
    PersistentJob.priority,
    PersistentJob.created_at,
)
Index("ix_persistent_jobs_heartbeat", PersistentJob.status, PersistentJob.heartbeat_at)


class AlertState(Base):
    __tablename__ = "alert_states"

    alert_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ok", server_default="ok")
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), default="me")
    keywords: Mapped[list[str]] = mapped_column(STR_ARRAY, default=list)
    notify_in_app: Mapped[bool] = mapped_column(default=True)
    notify_bid_deadline: Mapped[bool] = mapped_column(default=True)
    notify_email_digest: Mapped[bool] = mapped_column(default=False)


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16))  # daily | weekly | topic
    title: Mapped[str] = mapped_column(String(200))
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(8), default="完成")  # 生成中 | 完成 | 失败
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True)
    category: Mapped[str] = mapped_column(String(16), default="其他")  # 视觉/OCR | 大模型 | 电力AI应用 | 其他
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)          # 解决什么问题
    method: Mapped[str | None] = mapped_column(Text, nullable=True)           # 核心方法
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)       # 关键结论
    power_relevance: Mapped[str | None] = mapped_column(Text, nullable=True)  # 与电力场景的关联
    note: Mapped[str | None] = mapped_column(Text, nullable=True)             # 个人笔记
    status: Mapped[str] = mapped_column(String(8), default="生成中")  # 生成中 | 完成 | 失败
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
