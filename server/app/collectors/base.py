"""采集契约：采集器只负责「拿到原始条目 + 如实报告传输/解析状态」。

失败必须显式返回（transport/parse 状态），不能吞异常返回空列表——
否则信源挂掉会被显示成「健康但没新闻」。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from app.collectors.http import PoliteClient

TransportStatus = Literal["ok", "partial", "timeout", "http_error", "network_error"]
ParseStatus = Literal["ok", "empty", "schema_error", "parse_error"]


@dataclass
class RawItem:
    title: str
    url: str
    content_text: str | None = None
    content_html: str | None = None  # 未消毒，入库前统一消毒
    published_at: datetime | None = None
    external_id: str | None = None
    channel_hint: str | None = None  # 列表栏目给出的频道提示（如招标栏目）

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()


@dataclass
class CollectorResult:
    items: list[RawItem] = field(default_factory=list)
    transport_status: TransportStatus = "ok"
    parse_status: ParseStatus = "empty"
    error: str | None = None
    http_status: int | None = None

    @classmethod
    def ok(cls, items: list[RawItem], *, partial_error: str | None = None) -> CollectorResult:
        return cls(
            items=items,
            transport_status="partial" if partial_error else "ok",
            parse_status="ok" if items else "empty",
            error=partial_error,
        )

    @classmethod
    def fail(
        cls,
        transport: TransportStatus,
        error: str,
        *,
        http_status: int | None = None,
        parse: ParseStatus = "empty",
    ) -> CollectorResult:
        return cls(transport_status=transport, parse_status=parse, error=error[:500], http_status=http_status)

    @property
    def healthy(self) -> bool:
        return self.transport_status in ("ok", "partial") and self.parse_status in ("ok", "empty")


class Collector(Protocol):
    async def fetch(self, client: PoliteClient) -> CollectorResult: ...
