"""arXiv 论文采集器 —— 官方 API（国内可直连），每日一采。

按关键词组查询 cs.CV/cs.CL 最新提交，摘要作为 content 供评分器使用。
网络异常直接向上抛，由 ingest 的逐采集器容错兜底。
"""
from __future__ import annotations

import re

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import parse_datetime

API_URL = "https://export.arxiv.org/api/query"

# 查询侧关键词过滤（控制进量），可按需调整。
KEYWORDS = [
    "OCR", "document understanding", "text recognition", "object detection",
    "defect detection", "anomaly detection", "multimodal large language model",
    "vision-language model",
]


def _query() -> str:
    terms = " OR ".join(f'abs:"{k}"' for k in KEYWORDS)
    return f"(cat:cs.CV OR cat:cs.CL) AND ({terms})"


class ArxivCollector(BaseCollector):
    source_name = "arXiv"
    domain = "arxiv.org"
    channel = "前沿论文"
    tier = "T1"
    group = "papers"

    def __init__(self, limit: int = 30) -> None:
        self.limit = limit

    def fetch(self) -> CollectorResult:
        try:
            import feedparser
        except ImportError:
            return CollectorResult.parse_error("feedparser is unavailable")

        try:
            r = httpx.get(
                API_URL,
                params={
                    "search_query": _query(),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": self.limit,
                },
                timeout=30,
            )
        except httpx.TimeoutException as exc:
            return CollectorResult.timeout(str(exc))
        except httpx.HTTPError as exc:
            return CollectorResult.network_error(str(exc))
        if r.status_code >= 400:
            return CollectorResult.http_error(r.status_code, f"HTTP {r.status_code}")
        d = feedparser.parse(r.text)

        out: list[RawArticle] = []
        for e in d.entries:
            url = getattr(e, "id", "") or getattr(e, "link", "")
            title = re.sub(r"\s+", " ", getattr(e, "title", "")).strip()
            if not url or not title:
                continue
            arxiv_id = url.rsplit("/abs/", 1)[-1]
            pdf_url = next(
                (l.get("href") for l in getattr(e, "links", []) if l.get("title") == "pdf"),
                f"https://arxiv.org/pdf/{arxiv_id}",
            )
            label = (getattr(e, "published", "") or "")[:10] or None
            published_at = parse_datetime(getattr(e, "published", "") or getattr(e, "updated", ""))
            out.append(RawArticle(
                title=title,
                url=url,
                content=re.sub(r"\s+", " ", getattr(e, "summary", "")).strip(),
                channel=self.channel,
                kind="论文",
                meta={
                    "arxiv_id": arxiv_id,
                    "pdf_url": pdf_url,
                    "authors": [a.get("name", "") for a in getattr(e, "authors", [])][:6],
                },
                source_domain=self.domain,
                published_label=label,
                published_at=published_at,
            ))
        return CollectorResult.ok(items=out)
