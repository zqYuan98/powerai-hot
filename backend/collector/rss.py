"""Generic RSS / Atom collector."""
from __future__ import annotations

import calendar
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT, is_feed_response
from core.urlguard import validate_feed_url


MAX_REDIRECTS = 5


def _strip_html(text: str, limit: int = 1000) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _safe_error(message: object) -> str:
    text = str(message or "feed request failed")
    text = re.sub(r"://[^/@\s]+@", "://<redacted>@", text)
    text = re.sub(r"(?i)(token|key|secret|password)=([^&\s]+)", r"\1=<redacted>", text)
    return text[:500]


class RssCollector(BaseCollector):
    channel = "行业动态"

    def __init__(self, feed_url: str, source_name: str = "RSS", limit: int = 20,
                 tier: str = "T2") -> None:
        self.feed_url = feed_url
        self.source_name = source_name
        self.limit = limit
        self.tier = tier
        self.domain = urlparse(feed_url).netloc

    def fetch(self) -> CollectorResult:
        current_url = self.feed_url
        resp = None
        for hop in range(MAX_REDIRECTS + 1):
            try:
                # DNS/IP validation is repeated immediately before connect and
                # for every redirect hop. A malicious DNS server can still race
                # validation vs. connect; avoiding that entirely would require
                # binding httpx to the validated address while preserving Host/SNI.
                validate_feed_url(current_url)
            except ValueError as exc:
                return CollectorResult.schema_error(f"unsafe feed URL: {_safe_error(exc)}")
            try:
                resp = httpx.get(
                    current_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/plain",
                    },
                    timeout=15,
                    follow_redirects=False,
                )
            except httpx.TimeoutException as exc:
                return CollectorResult.timeout(_safe_error(exc))
            except httpx.HTTPError as exc:
                return CollectorResult.network_error(_safe_error(exc))

            if resp.status_code not in {301, 302, 303, 307, 308}:
                break
            location = resp.headers.get("location")
            if not location:
                return CollectorResult.schema_error("RSS redirect missing Location header")
            next_url = urljoin(current_url, location)
            if hop == MAX_REDIRECTS:
                return CollectorResult.schema_error("RSS redirect limit exceeded")
            current_url = next_url

        if resp is None:
            return CollectorResult.network_error("RSS request failed")
        if resp.status_code >= 400:
            return CollectorResult.http_error(resp.status_code, f"HTTP {resp.status_code}")
        if 300 <= resp.status_code < 400:
            return CollectorResult.schema_error(f"unsupported RSS redirect status {resp.status_code}")
        if not is_feed_response(resp.headers):
            return CollectorResult.schema_error("RSS response is not feed content")
        try:
            import feedparser
        except ImportError as exc:
            return CollectorResult.parse_error(f"feedparser unavailable: {exc}")
        try:
            parsed = feedparser.parse(resp.content)
        except Exception as exc:
            return CollectorResult.parse_error(str(exc))
        if getattr(parsed, "bozo", False):
            return CollectorResult.parse_error(str(getattr(parsed, "bozo_exception", "feed parse error")))

        out: list[RawArticle] = []
        for entry in parsed.entries[: self.limit]:
            title = (getattr(entry, "title", "") or "").strip()
            link = getattr(entry, "link", "") or ""
            if not title or not link:
                continue
            label = None
            published_at = None
            tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if tm:
                try:
                    label = time.strftime("%Y-%m-%d", tm)
                    published_at = datetime.fromtimestamp(calendar.timegm(tm), tz=timezone.utc)
                except Exception:
                    label = None
                    published_at = None
            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            rich = ""
            entry_content = getattr(entry, "content", None)
            if entry_content:
                try:
                    rich = entry_content[0].value or ""
                except (IndexError, AttributeError, TypeError):
                    rich = ""
            if not rich and "<" in raw_summary and len(raw_summary) > 500:
                rich = raw_summary
            out.append(RawArticle(
                title=title,
                url=link,
                content=_strip_html(raw_summary),
                content_html=rich or None,
                source_domain=self.domain,
                published_label=label,
                published_at=published_at,
                source_name=self.source_name,
                source_url=self.feed_url,
            ))
        return CollectorResult.ok(items=out)
