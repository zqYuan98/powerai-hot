"""Hugging Face Daily Papers 采集器 —— 官方 JSON API，每日一采。

国内访问不稳时在 .env 设 HF_ENDPOINT=https://hf-mirror.com。
同一论文可能与 arXiv 采集器重复（URL 不同），由 Phase 2 事件聚类折叠。
"""
from __future__ import annotations

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import parse_datetime
from core.config import settings


class HFPapersCollector(BaseCollector):
    source_name = "Hugging Face Papers"
    domain = "huggingface.co"
    channel = "前沿论文"
    tier = "T1"
    group = "papers"

    def __init__(self, limit: int = 30) -> None:
        self.limit = limit

    def fetch(self) -> CollectorResult:
        try:
            r = httpx.get(f"{settings.hf_endpoint}/api/daily_papers", timeout=30,
                          follow_redirects=True)
        except httpx.TimeoutException as exc:
            return CollectorResult.timeout(str(exc))
        except httpx.HTTPError as exc:
            # 国内直连 huggingface.co 会是 [Errno 101] Network is unreachable，
            # 需在 .env 设 HF_ENDPOINT=https://hf-mirror.com。把提示带进错误里，
            # 否则信源管理只显示一行 errno，看不出该怎么修。
            return CollectorResult.network_error(
                f"{exc}（若为国内网络，请设置 HF_ENDPOINT=https://hf-mirror.com）"
            )
        if r.status_code >= 400:
            return CollectorResult.http_error(r.status_code, f"HTTP {r.status_code}")
        try:
            rows = r.json()
        except ValueError as exc:
            return CollectorResult.parse_error(str(exc))
        if not isinstance(rows, list):
            return CollectorResult.schema_error("daily_papers payload must be a list")

        out: list[RawArticle] = []
        for row in rows[: self.limit]:
            paper = row.get("paper") or {}
            pid = paper.get("id") or ""
            title = (paper.get("title") or "").strip()
            if not pid or not title:
                continue
            out.append(RawArticle(
                title=title,
                url=f"https://huggingface.co/papers/{pid}",
                content=(paper.get("summary") or "").strip(),
                channel=self.channel,
                kind="论文",
                meta={
                    "arxiv_id": pid,
                    "pdf_url": f"https://arxiv.org/pdf/{pid}",
                    "hf_url": f"https://huggingface.co/papers/{pid}",
                    "authors": [a.get("name", "") for a in paper.get("authors", [])][:6],
                },
                source_domain=self.domain,
                published_label=(row.get("publishedAt") or "")[:10] or None,
                published_at=parse_datetime(row.get("publishedAt") or paper.get("publishedAt")),
            ))
        return CollectorResult.ok(items=out)
