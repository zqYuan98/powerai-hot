"""南方电网官网新闻采集器。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT

LIST_URL = "https://www.csg.cn/"
ARTICLE_RE = re.compile(
    r"^https://www\.csg\.cn/(?:xwzx/.+|index/jdxw)/(\d{6}/)?t(\d{8})_\d+\.html$"
)


class SouthernGridCollector(BaseCollector):
    source_name = "南方电网"
    source_url = LIST_URL
    domain = "csg.cn"
    channel = "行业动态"
    tier = "T1"

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit

    def fetch(self) -> CollectorResult:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return CollectorResult.parse_error("BeautifulSoup is unavailable")
        try:
            response = httpx.get(
                LIST_URL,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                timeout=20,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return CollectorResult.timeout("南方电网页面请求超时")
        except httpx.HTTPStatusError as exc:
            return CollectorResult.http_error(exc.response.status_code, "南方电网页面 HTTP 错误")
        except httpx.RequestError as exc:
            return CollectorResult.network_error(str(exc))

        soup = BeautifulSoup(response.content, "lxml")
        items: list[RawArticle] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            url = urljoin(LIST_URL, anchor["href"])
            match = ARTICLE_RE.match(url)
            if not match or len(title) < 8 or url in seen:
                continue
            seen.add(url)
            date_text = match.group(2)
            items.append(RawArticle(
                title=title,
                url=url,
                channel=self.channel,
                org="南方电网",
                source_domain=self.domain,
                source_name=self.source_name,
                source_url=self.source_url,
                published_at=datetime.strptime(date_text, "%Y%m%d").replace(tzinfo=timezone.utc),
                provenance={"attribution": "中国南方电网公开网站", "list_url": LIST_URL},
            ))
            if len(items) >= self.limit:
                break
        return CollectorResult.ok(items=items)
