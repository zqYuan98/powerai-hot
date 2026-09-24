"""国家能源局公开信息采集器。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT

LIST_URL = "https://www.nea.gov.cn/"
ARTICLE_RE = re.compile(
    r"^https?://www\.nea\.gov\.cn/(\d{4})(\d{2})(\d{2})/[0-9a-f]+/c\.html$",
    re.IGNORECASE,
)


class NeaCollector(BaseCollector):
    source_name = "国家能源局"
    source_url = LIST_URL
    domain = "nea.gov.cn"
    channel = "政策法规"
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
            return CollectorResult.timeout("国家能源局页面请求超时")
        except httpx.HTTPStatusError as exc:
            return CollectorResult.http_error(exc.response.status_code, "国家能源局页面 HTTP 错误")
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
            year, month, day = (int(value) for value in match.groups())
            items.append(RawArticle(
                title=title,
                url=url.replace("http://", "https://", 1),
                channel=self.channel,
                org="国家能源局",
                source_domain=self.domain,
                source_name=self.source_name,
                source_url=self.source_url,
                published_at=datetime(year, month, day, tzinfo=timezone.utc),
                provenance={"attribution": "国家能源局公开网站", "list_url": LIST_URL},
            ))
            if len(items) >= self.limit:
                break
        return CollectorResult.ok(items=items)
