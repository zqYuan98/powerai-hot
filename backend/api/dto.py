"""Pydantic request/response DTOs shared by the API routers."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# 非 Optional 字段的类型默认值：数据库里这些列若为 NULL（PG 的 ARRAY、旧数据、
# 手工 SQL 都可能），model_validate 会抛 ValidationError 拖垮整个列表接口 →
# 前端全量回退空状态。入模型前把 NULL 补成默认值，让单条脏数据不影响整表。
_ARTICLE_NULL_DEFAULTS = {
    "tags": list, "channel": lambda: "行业动态", "hot": lambda: False,
    "view_count": lambda: 0, "relevance_score": lambda: 0, "curated": lambda: False,
    "kind": lambda: "资讯", "tier": lambda: "T2", "scored": lambda: False,
    "processing_status": lambda: "processed", "scored_by": lambda: "unscored",
    "is_cluster_main": lambda: True, "related_count": lambda: 0,
}


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _fill_nulls(cls, data):
        if not isinstance(data, dict):  # ORM 对象：转成可改写的 dict
            data = {k: getattr(data, k, None) for k in cls.model_fields}
        for key, factory in _ARTICLE_NULL_DEFAULTS.items():
            if data.get(key) is None:
                data[key] = factory()
        return data

    id: int
    title: str
    summary: Optional[str] = None
    tags: list[str] = []
    channel: str
    org: Optional[str] = None
    hot: bool = False
    deadline_days: Optional[int] = None
    source_domain: Optional[str] = None
    url: Optional[str] = None
    published_label: Optional[str] = None
    # 时间窗筛选用：published_at 源侧发布时间（可空），crawled_at 入库时间（必有，UTC naive）
    published_at: Optional[datetime] = None
    crawled_at: Optional[datetime] = None
    view_count: int = 0
    relevance_score: int = 0
    recommend_reason: Optional[str] = None
    curated: bool = False
    # 双轴：cross_score = √(ai_relevance × power_relevance)，axis ∈ 交叉/AI/行业/弱
    cross_score: int = 0
    axis: str = "弱"
    kind: str = "资讯"
    meta: Optional[dict] = None
    tier: str = "T2"
    scored: bool = False
    processing_status: str = "processed"
    scored_by: str = "unscored"
    dim_scores: Optional[dict] = None
    cluster_id: Optional[str] = None
    is_cluster_main: bool = True
    related_count: int = 0
    noise_reason: Optional[str] = None
    primary_thread_id: Optional[int] = None
    thread_affinity: Optional[dict] = None


class ResearchThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    keywords: list[str]
    weight: float
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResearchThreadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    keywords: list[str] = Field(min_length=1, max_length=30)
    weight: float = Field(ge=0.1, le=2.0)
    status: Literal["active", "paused"] = "active"

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        clean, seen = [], set()
        for keyword in value:
            normalized = keyword.strip()
            if not normalized or len(normalized) > 80:
                raise ValueError("关键词必须为 1-80 个字符")
            if normalized.casefold() not in seen:
                clean.append(normalized)
                seen.add(normalized.casefold())
        if not clean:
            raise ValueError("至少需要一个关键词")
        return clean


class ResearchThreadUpdate(ResearchThreadCreate):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    keywords: Optional[list[str]] = Field(default=None, min_length=1, max_length=30)
    weight: Optional[float] = Field(default=None, ge=0.1, le=2.0)
    status: Optional[Literal["active", "paused"]] = None


class ArticleDetail(ArticleOut):
    """详情页专用：多带消毒后的富文本正文；列表接口禁止使用（payload 纪律）。"""
    content_html: Optional[str] = None


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    next_cursor: Optional[str] = None
    has_more: bool
    total: int


class ArticleFreshness(BaseModel):
    latest_crawled_at: Optional[datetime] = None
    added_24h: int
    curated_24h: int


class TimelineBucket(BaseModel):
    ts: datetime          # 小时桶起点（UTC）
    count: int            # 该小时入库数
    curated: int          # 其中精选数


class ArticleTimeline(BaseModel):
    latest_crawled_at: Optional[datetime] = None
    buckets: list[TimelineBucket]


class SubscriptionHit(BaseModel):
    article: ArticleOut
    keyword: str


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    type: str
    status: str
    submitted_by: Optional[str] = None
    # 信源管理页展示：分级与抓取健康（列在 Source 表中已存在）
    tier: Optional[str] = "T2"
    last_status: Optional[str] = None  # ok | error | None(从未抓取)
    last_error: Optional[str] = None
    last_crawled_at: Optional[datetime] = None
    # 由 API 层计算（api/sources.py::_to_out），不是表字段——
    # 单一事实在 services/ingest.py，前端不再硬编码内置名单/抓取规则
    builtin: bool = False    # 是否代码内置采集器（始终参与采集、不可停用）
    crawlable: bool = False  # 已采纳后是否会被 build_collectors 实际抓取
    # 产出价值：判断信源该留该砍的依据（抓取状态 ok 不代表有价值）
    article_count: int = 0
    noise_pct: int = 0
    curated_count: int = 0
    power_count: int = 0


class SourceCreate(BaseModel):
    name: str
    url: str
    type: str = "网站"
    reason: Optional[str] = None


class SourceSubmissionCreate(BaseModel):
    """Strict employee-facing source submission payload.

    This deliberately remains separate from ``SourceCreate`` so the existing
    administrator endpoint keeps its backwards-compatible request shape,
    while employee submissions cannot smuggle management flags such as
    ``active`` into the write path.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=500)
    type: Literal["网站", "公众号", "RSS"] = "网站"
    reason: Optional[str] = Field(default=None, min_length=1, max_length=1000)


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keywords: list[str] = []
    notify_in_app: bool
    notify_bid_deadline: bool
    notify_email_digest: bool


class SubscriptionUpdate(BaseModel):
    keywords: Optional[list[str]] = None
    notify_in_app: Optional[bool] = None
    notify_bid_deadline: Optional[bool] = None
    notify_email_digest: Optional[bool] = None
