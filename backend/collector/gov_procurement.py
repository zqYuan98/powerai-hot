"""中国政府采购网电力、能源和智能化招标采集器。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT

LIST_URLS = (
    "https://www.ccgp.gov.cn/cggg/zygg/gkzb/",
    "https://www.ccgp.gov.cn/cggg/dfgg/gkzb/",
)
ARTICLE_RE = re.compile(
    r"^https://www\.ccgp\.gov\.cn/cggg/(?:zygg|dfgg)/gkzb/\d{6}/t(\d{8})_\d+\.htm$"
)
RELEVANT_KEYWORDS = (
    "电力", "电网", "能源", "输电", "变电", "配电", "发电", "储能",
    "光伏", "风电", "充电", "智能", "人工智能", "无人机", "巡检",
    "数字化", "信息化", "通信", "视频", "视觉", "OCR", "大模型",
)


class GovProcurementCollector(BaseCollector):
    source_name = "中国政府采购网"
    source_url = "https://www.ccgp.gov.cn/"
    domain = "ccgp.gov.cn"
    channel = "招标公告"
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
        reached_source = False
        last_error: CollectorResult | None = None
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
                last_error = CollectorResult.timeout("中国政府采购网页面请求超时")
                continue
            except httpx.HTTPStatusError as exc:
                last_error = CollectorResult.http_error(exc.response.status_code, "中国政府采购网 HTTP 错误")
                continue
            except httpx.RequestError as exc:
                last_error = CollectorResult.network_error(str(exc))
                continue

            soup = BeautifulSoup(response.content, "lxml")
            for anchor in soup.find_all("a", href=True):
                title = " ".join(anchor.get_text(" ", strip=True).split()).rstrip(".")
                url = urljoin(list_url, anchor["href"])
                match = ARTICLE_RE.match(url)
                if (
                    not match
                    or len(title) < 10
                    or not any(keyword.casefold() in title.casefold() for keyword in RELEVANT_KEYWORDS)
                    or url in seen
                ):
                    continue
                seen.add(url)
                items.append(RawArticle(
                    title=title,
                    url=url,
                    channel=self.channel,
                    org="中国政府采购网",
                    source_domain=self.domain,
                    source_name=self.source_name,
                    source_url=self.source_url,
                    published_at=datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=timezone.utc),
                    provenance={"attribution": "中国政府采购网公开公告", "list_url": list_url},
                ))
                if len(items) >= self.limit:
                    return CollectorResult.ok(items=items)

        if not reached_source and last_error is not None:
            return last_error
        return CollectorResult.ok(items=items)
