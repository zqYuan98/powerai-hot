"""国家电网公开新闻采集器。

主站启用了 JavaScript 风控，服务端直抓长期返回 412。华北分部站点属于
``sgcc.com.cn`` 官方域名且提供静态列表页，因此用它承接国网一手动态。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT

LIST_URLS = (
    "http://www.nc.sgcc.com.cn/zxzx/gsxw/",
    "http://www.nc.sgcc.com.cn/zxzx/zbdt/",
)
ARTICLE_RE = re.compile(
    r"^http://www\.nc\.sgcc\.com\.cn/zxzx/(?:gsxw|zbdt)/(\d{4})/(\d{2})/\d+\.shtml$"
)


class SgccNewsCollector(BaseCollector):
    source_name = "国家电网"
    source_url = "http://www.nc.sgcc.com.cn/"
    domain = "nc.sgcc.com.cn"
    channel = "行业动态"
    tier = "T1"

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit

    def fetch(self) -> CollectorResult:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return CollectorResult.parse_error("BeautifulSoup is unavailable")

        items: list[RawArticle] = []
        seen: set[str] = set()
        last_error: CollectorResult | None = None
        reached_source = False
        for list_url in LIST_URLS:
            try:
                response = httpx.get(
                    list_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                    timeout=20,
                    follow_redirects=True,
                )
                response.raise_for_status()
                reached_source = True
            except httpx.TimeoutException:
                last_error = CollectorResult.timeout("国家电网页面请求超时")
                continue
            except httpx.HTTPStatusError as exc:
                last_error = CollectorResult.http_error(exc.response.status_code, "国家电网页面 HTTP 错误")
                continue
            except httpx.RequestError as exc:
                last_error = CollectorResult.network_error(str(exc))
                continue

            soup = BeautifulSoup(response.content, "lxml")
            for anchor in soup.find_all("a", href=True):
                title = " ".join(anchor.get_text(" ", strip=True).split())
                url = urljoin(list_url, anchor["href"])
                match = ARTICLE_RE.match(url)
                if not match or len(title) < 8 or url in seen:
                    continue
                seen.add(url)
                year, month = match.groups()
                published_at = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
                items.append(RawArticle(
                    title=title,
                    url=url,
                    channel=self.channel,
                    org="国家电网",
                    source_domain=self.domain,
                    source_name=self.source_name,
                    source_url=self.source_url,
                    published_at=published_at,
                    provenance={"attribution": "国家电网华北分部公开网站", "list_url": list_url},
                ))
                if len(items) >= self.limit:
                    return CollectorResult.ok(items=items)

        if not reached_source and last_error is not None:
            return last_error
        return CollectorResult.ok(items=items)
