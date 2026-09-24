"""南方电网供应链统一服务平台采购公告采集器。"""
from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT

LIST_URL = "https://www.bidding.csg.cn/zbcg/index.jhtml"
ARTICLE_RE = re.compile(
    r"^https://www\.bidding\.csg\.cn/"
    r"(?:zbgg|fzbgg|lxcggg|zbhxrgs|zbcg|yjzjgg|xygg)/\d+\.jhtml$"
)


class SouthernGridBiddingCollector(BaseCollector):
    source_name = "南方电网供应链"
    source_url = "https://www.bidding.csg.cn/"
    domain = "bidding.csg.cn"
    channel = "招标公告"
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
                timeout=25,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return CollectorResult.timeout("南方电网供应链页面请求超时")
        except httpx.HTTPStatusError as exc:
            return CollectorResult.http_error(exc.response.status_code, "南方电网供应链 HTTP 错误")
        except httpx.RequestError as exc:
            return CollectorResult.network_error(str(exc))

        soup = BeautifulSoup(response.content, "lxml")
        items: list[RawArticle] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split()).rstrip(".")
            url = urljoin(LIST_URL, anchor["href"])
            if (
                not ARTICLE_RE.match(url)
                or len(title) < 14
                or title.startswith("[")
                or url in seen
            ):
                continue
            seen.add(url)
            items.append(RawArticle(
                title=title,
                url=url,
                channel=self.channel,
                org="南方电网",
                source_domain=self.domain,
                source_name=self.source_name,
                source_url=self.source_url,
                provenance={"attribution": "南方电网供应链统一服务平台", "list_url": LIST_URL},
            ))
            if len(items) >= self.limit:
                break
        return CollectorResult.ok(items=items)
