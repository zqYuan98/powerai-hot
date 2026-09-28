"""通用 RSS/Atom 采集器。每一跳重定向都重新做 SSRF 校验。"""
from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

import feedparser

from app.collectors.base import CollectorResult, RawItem
from app.collectors.http import FetchError, PoliteClient
from app.collectors.textutil import clean_text
from app.collectors.urlguard import UnsafeUrl, validate_public_url

MAX_REDIRECTS = 5
FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5"


def _redact(message: object) -> str:
    text = re.sub(r"://[^/@\s]+@", "://<redacted>@", str(message))
    return re.sub(r"(?i)(token|key|secret|password)=([^&\s]+)", r"\1=<redacted>", text)[:300]


def _strip_html(value: str, limit: int = 1500) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", value))[:limit]


class RssCollector:
    def __init__(self, feed_url: str, *, limit: int = 30) -> None:
        self.feed_url = feed_url
        self.limit = limit

    async def fetch(self, client: PoliteClient) -> CollectorResult:
        url = self.feed_url
        for hop in range(MAX_REDIRECTS + 1):
            try:
                await validate_public_url(url)
                page = await client.get(url, headers={"Accept": FEED_ACCEPT},
                                        follow_redirects=False, raise_for_status=False)
            except UnsafeUrl as exc:
                return CollectorResult.fail("ok", f"不安全的地址：{exc}", parse="schema_error")
            except FetchError as exc:
                return CollectorResult.fail(exc.kind, _redact(exc), http_status=exc.status)
            if page.status in (301, 302, 303, 307, 308):
                location = page.headers.get("location")
                if not location or hop == MAX_REDIRECTS:
                    return CollectorResult.fail("ok", "重定向异常", parse="schema_error")
                url = urljoin(url, location)
                continue
            break
        if page.status >= 400:
            return CollectorResult.fail("http_error", f"HTTP {page.status}", http_status=page.status)

        parsed = feedparser.parse(page.content)
        if not parsed.entries:
            if getattr(parsed, "bozo", False):
                return CollectorResult.fail("ok", _redact(parsed.get("bozo_exception", "feed 解析失败")),
                                            parse="parse_error")
            return CollectorResult.ok([])

        items: list[RawItem] = []
        for entry in parsed.entries[: self.limit]:
            title = clean_text(entry.get("title"))
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            published = None
            if tm := entry.get("published_parsed") or entry.get("updated_parsed"):
                published = datetime.fromtimestamp(calendar.timegm(tm), tz=UTC)
            summary = entry.get("summary") or entry.get("description") or ""
            rich = ""
            if entry.get("content"):
                rich = entry["content"][0].get("value") or ""
            if not rich and "<" in summary and len(summary) > 500:
                rich = summary
            items.append(RawItem(
                title=title,
                url=link,
                content_text=_strip_html(rich or summary) or None,
                content_html=rich or None,
                published_at=published,
                external_id=entry.get("id"),
            ))
        return CollectorResult.ok(items)
