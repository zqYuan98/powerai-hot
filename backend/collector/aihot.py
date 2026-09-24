"""AI HOT public API collector."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT, canonical_url, is_json_response, parse_datetime

AIHOT_PUBLIC_ITEMS_URL = "https://aihot.virxact.com/api/public/items"


class AihotCollector(BaseCollector):
    source_name = "AI HOT"
    source_url = "https://aihot.virxact.com"
    domain = "aihot.virxact.com"
    channel = "大模型动态"
    tier = "T1"
    group = "news"

    def __init__(self, *, api_url: str = AIHOT_PUBLIC_ITEMS_URL, limit: int = 30) -> None:
        self.api_url = api_url
        self.limit = limit

    def fetch(self) -> CollectorResult:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        params = {
            "mode": "selected",
            "since": since.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "take": self.limit,
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            resp = httpx.get(self.api_url, params=params, headers=headers, timeout=15, follow_redirects=True)
        except httpx.TimeoutException as exc:
            return CollectorResult.timeout(str(exc))
        except httpx.HTTPError as exc:
            return CollectorResult.network_error(str(exc))
        if resp.status_code >= 400:
            return CollectorResult.http_error(resp.status_code, f"HTTP {resp.status_code}")
        if not is_json_response(resp.headers):
            return CollectorResult.schema_error("AIHOT response is not JSON")
        try:
            payload = resp.json()
        except ValueError as exc:
            return CollectorResult.parse_error(str(exc))
        rows = payload.get("items") or payload.get("data") or payload.get("results")
        if not isinstance(rows, list):
            return CollectorResult.schema_error("AIHOT payload missing items")
        items: list[RawArticle] = []
        for row in rows[: self.limit]:
            if not isinstance(row, dict):
                continue
            title = (row.get("title") or "").strip()
            url = row.get("url") or row.get("original_url") or row.get("link")
            if not title or not url:
                continue
            detail_url = row.get("permalink") or row.get("detail_url") or row.get("detailUrl")
            attribution = row.get("attribution") or "AIHOT public API"
            source_name = row.get("source") or self.source_name
            items.append(RawArticle(
                title=title,
                url=canonical_url(url),
                content=(row.get("summary") or row.get("description") or "").strip(),
                channel=self.channel,
                source_name=source_name,
                source_url=self.source_url,
                source_domain=self.domain,
                source_external_id=str(row.get("id") or row.get("external_id") or ""),
                published_at=parse_datetime(row.get("publishedAt") or row.get("published_at") or row.get("created_at")),
                provenance={
                    "detail_url": detail_url,
                    "attribution": attribution,
                    "category": row.get("category"),
                },
            ))
        return CollectorResult.ok(items=items)
