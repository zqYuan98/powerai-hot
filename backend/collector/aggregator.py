"""ai-news-aggregator latest-24h.json collector."""
from __future__ import annotations

import httpx
from urllib.parse import urlsplit, urlunsplit

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT, canonical_url, is_json_response, parse_datetime

AGGREGATOR_LATEST_24H_URL = "https://raw.githubusercontent.com/SuYxh/ai-news-aggregator/main/data/latest-24h.json"
AGGREGATOR_JSDELIVR_URL = "https://cdn.jsdelivr.net/gh/SuYxh/ai-news-aggregator@main/data/latest-24h.json"


def _origin(url: str) -> tuple[str | None, str | None]:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return None, None
    domain = parsed.hostname.lower() if parsed.hostname else parsed.netloc.lower()
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", "")), domain


def _trusted_json_content_type(url: str, headers: dict, text: str) -> bool:
    if is_json_response(headers):
        return True
    content_type = (headers.get("content-type") or "").lower()
    if url == AGGREGATOR_LATEST_24H_URL and "text/plain" in content_type:
        return not text.lstrip().lower().startswith("<!doctype") and not text.lstrip().lower().startswith("<html")
    return False


class AggregatorCollector(BaseCollector):
    source_name = "ai-news-aggregator"
    source_url = "https://github.com/SuYxh/ai-news-aggregator"
    domain = "github.com"
    channel = "大模型动态"
    tier = "T1.5"
    group = "news"

    def __init__(self, *, url: str = AGGREGATOR_LATEST_24H_URL, limit: int = 50) -> None:
        self.url = url
        self.limit = limit

    def fetch(self) -> CollectorResult:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        urls = [self.url]
        if self.url == AGGREGATOR_LATEST_24H_URL:
            urls.append(AGGREGATOR_JSDELIVR_URL)
        rows = None
        feed_url = self.url
        last_error: CollectorResult | None = None
        for candidate_url in urls:
            try:
                resp = httpx.get(candidate_url, headers=headers, timeout=15, follow_redirects=True)
            except httpx.TimeoutException as exc:
                last_error = CollectorResult.timeout(str(exc))
                continue
            except httpx.HTTPError as exc:
                last_error = CollectorResult.network_error(str(exc))
                continue
            if resp.status_code >= 400:
                last_error = CollectorResult.http_error(resp.status_code, f"HTTP {resp.status_code}")
                continue
            if not _trusted_json_content_type(candidate_url, resp.headers, resp.text):
                last_error = CollectorResult.schema_error("aggregator response is not JSON")
                continue
            try:
                payload = resp.json()
            except ValueError as exc:
                last_error = CollectorResult.parse_error(str(exc))
                continue
            candidate_rows = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(candidate_rows, list):
                last_error = CollectorResult.schema_error("aggregator payload must be a list or items object")
                continue
            rows = candidate_rows
            feed_url = candidate_url
            break
        if rows is None:
            return last_error or CollectorResult.schema_error("aggregator request failed")
        items: list[RawArticle] = []
        for row in rows[: self.limit]:
            if not isinstance(row, dict):
                continue
            title = (row.get("title") or "").strip()
            url = row.get("url") or row.get("link")
            if not title or not url:
                continue
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            source_url, source_domain = _origin(canonical_url(url))
            source_name = (
                row.get("site_name")
                or source.get("name")
                or (row.get("source") if isinstance(row.get("source"), str) else None)
                or row.get("source_name")
                or self.source_name
            )
            items.append(RawArticle(
                title=title,
                url=canonical_url(url),
                content=(row.get("summary") or row.get("description") or "").strip(),
                channel=row.get("channel") or self.channel,
                source_name=source_name,
                source_url=source.get("url") or source_url or self.source_url,
                source_domain=source_domain,
                source_external_id=str(row.get("id") or row.get("guid") or ""),
                published_at=parse_datetime(row.get("published_at") or row.get("publishedAt") or row.get("date")),
                provenance={
                    "aggregator": self.source_name,
                    "feed_url": feed_url,
                    "site_id": row.get("site_id"),
                    "site_name": row.get("site_name"),
                    "source": row.get("source"),
                    "first_seen_at": row.get("first_seen_at"),
                    "last_seen_at": row.get("last_seen_at"),
                },
            ))
        return CollectorResult.ok(items=items)
