"""爬虫基类 — 各信源采集器继承此类。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class RawArticle:
    title: str
    url: str
    content: str = ""
    content_html: str | None = None  # 原始富文本（未消毒；ingest 统一消毒后入库）
    channel: str = "行业动态"
    org: str | None = None
    source_domain: str | None = None
    published_label: str | None = None
    published_at: datetime | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_external_id: str | None = None
    provenance: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    kind: str = "资讯"  # 资讯 | 论文 | 案例
    meta: dict = field(default_factory=dict)

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()


TransportStatus = Literal["ok", "timeout", "http_error", "network_error"]
ParseStatus = Literal["ok", "empty", "schema_error", "parse_error"]


@dataclass
class CollectorResult:
    """Structured collector contract.

    ``items=[]`` with ``ok/empty`` means the source was reachable but had no
    new rows. Transport and parse failures are explicit so ingest can record an
    auditable SourceRun instead of treating ``[]`` as success.
    """

    items: list[RawArticle] = field(default_factory=list)
    transport_status: TransportStatus = "ok"
    parse_status: ParseStatus = "empty"
    error_summary: str | None = None
    http_status: int | None = None

    @classmethod
    def ok(cls, *, items: list[RawArticle]) -> "CollectorResult":
        return cls(items=items, transport_status="ok", parse_status="ok" if items else "empty")

    @classmethod
    def timeout(cls, message: str = "timeout") -> "CollectorResult":
        return cls(transport_status="timeout", parse_status="empty", error_summary=message)

    @classmethod
    def http_error(cls, status_code: int, message: str = "http error") -> "CollectorResult":
        return cls(transport_status="http_error", parse_status="empty", http_status=status_code, error_summary=message)

    @classmethod
    def network_error(cls, message: str = "network error") -> "CollectorResult":
        return cls(transport_status="network_error", parse_status="empty", error_summary=message)

    @classmethod
    def schema_error(cls, message: str = "schema error") -> "CollectorResult":
        return cls(transport_status="ok", parse_status="schema_error", error_summary=message)

    @classmethod
    def parse_error(cls, message: str = "parse error") -> "CollectorResult":
        return cls(transport_status="ok", parse_status="parse_error", error_summary=message)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


class BaseCollector:
    """Subclasses set ``source_name``/``domain`` and implement ``fetch``."""

    source_name: str = "base"
    source_url: str = ""
    domain: str = ""
    channel: str = "行业动态"
    tier: str = "T2"      # 信源分级：T1 | T1.5 | T2
    group: str = "news"   # 调度分组：news(每小时) | papers(每日)

    def fetch(self) -> CollectorResult:
        """Return a CollectorResult for this run. Override in subclasses.

        Always return CollectorResult, never a bare list: ingest records source
        health from the transport/parse status, so a collector that swallows
        failures and returns ``[]`` shows up as a healthy source with no news.

        Real implementations use Playwright (dynamic pages) or
        httpx + BeautifulSoup4 (static pages), respecting robots.txt and
        the ≥5 min/site crawl gap from the design doc.
        """
        raise NotImplementedError
