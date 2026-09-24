"""AI Daily Frontier 的 GitHub Trending 只读快照采集器。"""
from __future__ import annotations

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT, canonical_url, is_json_response, parse_datetime

SNAPSHOT_URL = "https://www.gdufe888.top/api/sources/github-daily/latest"
RELEVANCE_TERMS = (
    " ai ", "artificial intelligence", "machine learning", "deep learning",
    "foundation model", "large language model", "computer vision",
    "llm", "gpt", "claude", "gemini", "deepseek", "qwen", "agent",
    "neural", "diffusion", "rag", "ocr", "vision", "robot",
    "人工智能", "大模型", "模型", "智能体", "机器学习", "深度学习",
    "计算机视觉", "视觉", "识别", "机器人", "电网", "电力", "能源",
)


def _is_relevant_repo(*values: str) -> bool:
    text = f" {' '.join(values).casefold()} "
    return any(term in text for term in RELEVANCE_TERMS)


class FrontierSnapshotCollector(BaseCollector):
    source_name = "GitHub Trending"
    source_url = "https://github.com/wenbochang888/github-trending-spider"
    domain = "github.com"
    channel = "落地案例"
    tier = "T2"

    def __init__(self, limit: int = 20, url: str = SNAPSHOT_URL) -> None:
        self.limit = limit
        self.url = url

    def fetch(self) -> CollectorResult:
        try:
            response = httpx.get(
                self.url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=20,
                follow_redirects=True,
            )
        except httpx.TimeoutException:
            return CollectorResult.timeout("GitHub Trending 快照请求超时")
        except httpx.RequestError as exc:
            return CollectorResult.network_error(str(exc))
        if response.status_code >= 400:
            return CollectorResult.http_error(response.status_code, "GitHub Trending 快照 HTTP 错误")
        if not is_json_response(response.headers):
            return CollectorResult.schema_error("GitHub Trending 快照不是 JSON")
        try:
            payload = response.json()
        except ValueError:
            return CollectorResult.schema_error("GitHub Trending 快照 JSON 无效")
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return CollectorResult.schema_error("GitHub Trending 快照缺少 items")

        generated_at = parse_datetime(payload.get("generated_at"))
        items: list[RawArticle] = []
        for row in payload["items"]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            url = canonical_url(str(row.get("url") or ""))
            if not title or not url.startswith(("http://", "https://")):
                continue
            chinese_summary = str(row.get("chinese_summary") or "").strip()
            original_summary = str(row.get("original_summary") or "").strip()
            if not _is_relevant_repo(title, chinese_summary, original_summary):
                continue
            meta = dict(row.get("meta") or {})
            meta["lock_channel"] = True
            items.append(RawArticle(
                title=title,
                url=url,
                content=chinese_summary or original_summary,
                channel=self.channel,
                kind="案例",
                org="GitHub",
                source_domain=self.domain,
                source_name=self.source_name,
                source_url=self.source_url,
                source_external_id=title,
                published_at=parse_datetime(row.get("published_at")) or generated_at,
                meta=meta,
                provenance={
                    "attribution": "github-trending-spider public snapshot",
                    "snapshot_url": self.url,
                },
            ))
            if len(items) >= self.limit:
                break
        return CollectorResult.ok(items=items)
