"""配置驱动的列表页采集器。

旧版 6 个电力采集器（北极星/能源局/国网/南网/政采/南网供应链）的逻辑完全同构：
抓列表页 → 用正则挑文章链接 → 从 URL 或邻近文本取日期 → 可选标题关键词过滤。
这里把它收敛成一个实现，站点差异全部写在 sources.yaml 的 config 里。
"""
from __future__ import annotations

import re
from functools import cached_property
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.collectors.base import CollectorResult, RawItem
from app.collectors.http import FetchError, PoliteClient
from app.collectors.textutil import clean_text, date_from_groups, parse_cn_datetime


class ListPage(BaseModel):
    url: str
    channel: str | None = None  # 该栏目的频道提示（例如招标栏目 → tender）


class HtmlListConfig(BaseModel):
    lists: list[ListPage] = Field(min_length=1)
    # 对绝对 URL 做 fullmatch；命名分组 y/m/d 用于提取发布日期（d 可缺省）
    link_pattern: str
    min_title_len: int = 8
    title_keywords: list[str] = Field(default_factory=list)  # 非空时标题须命中任一
    skip_title_prefixes: list[str] = Field(default_factory=list)
    limit_per_list: int = 30
    https_upgrade: bool = False
    date_from_parent: bool = False  # 优先从链接所在行的文本解析日期，失败再用 URL 分组

    @cached_property
    def link_re(self) -> re.Pattern[str]:
        return re.compile(self.link_pattern)


class HtmlListCollector:
    def __init__(self, config: HtmlListConfig) -> None:
        self.config = config

    async def fetch(self, client: PoliteClient) -> CollectorResult:
        cfg = self.config
        items: list[RawItem] = []
        seen: set[str] = set()
        failures: list[FetchError] = []
        for page_cfg in cfg.lists:
            try:
                page = await client.get(page_cfg.url)
            except FetchError as exc:
                failures.append(exc)
                continue
            items.extend(self._parse(page.text, page.url, page_cfg, seen))

        if failures and len(failures) == len(cfg.lists):
            first = failures[0]
            return CollectorResult.fail(
                first.kind, "全部列表页失败：" + "；".join(str(f) for f in failures), http_status=first.status
            )
        partial = "部分列表页失败：" + "；".join(str(f) for f in failures) if failures else None
        return CollectorResult.ok(items, partial_error=partial)

    def _parse(self, html: str, base_url: str, page_cfg: ListPage, seen: set[str]) -> list[RawItem]:
        cfg = self.config
        soup = BeautifulSoup(html, "lxml")
        out: list[RawItem] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"]).strip()
            url = urljoin(base_url, href)
            if cfg.https_upgrade and url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            match = cfg.link_re.fullmatch(url)
            if not match or url in seen:
                continue
            title = clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True))).rstrip(".…")
            if len(title) < cfg.min_title_len:
                continue
            if any(title.startswith(p) for p in cfg.skip_title_prefixes):
                continue
            if cfg.title_keywords and not any(k.casefold() in title.casefold() for k in cfg.title_keywords):
                continue
            # 列表行上的日期通常比 URL 更精确（部分站点 URL 只有年月）
            published = None
            if cfg.date_from_parent and anchor.parent is not None:
                published = parse_cn_datetime(anchor.parent.get_text(" ", strip=True))
            published = published or date_from_groups(match.groupdict())
            seen.add(url)
            out.append(RawItem(title=title, url=url, published_at=published, channel_hint=page_cfg.channel))
            if len(out) >= cfg.limit_per_list:
                break
        return out
