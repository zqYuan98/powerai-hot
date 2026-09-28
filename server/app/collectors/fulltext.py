"""正文回捞：列表页只给标题的站点，补抓详情页正文。

选择器实测自真实详情页（2026-07-26，迁移自旧版 collector/fulltext.py）。
信源可在 config.fulltext_selectors 里追加自己的选择器。
已知限制：news.bjx.com.cn 详情页为 JS 反爬，纯 HTTP 拿不到正文，因此不在白名单内。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.collectors.http import FetchError, PoliteClient
from app.collectors.textutil import clean_text
from app.core.htmlsanitize import sanitize_html

DOMAIN_SELECTORS: dict[str, tuple[str, ...]] = {
    "www.csg.cn": ("#ArtText", "div.TRS_Editor", "#articleText", "div.con-right"),
    "bidding.csg.cn": ("div.Content", "div.Section0", "div.s-content"),
    "www.bidding.csg.cn": ("div.Content", "div.Section0", "div.s-content"),
    "www.ccgp.gov.cn": ("div.vF_detail_content", "div.vF_deail_maincontent"),
    "www.nea.gov.cn": ("div.article-content", "div.content", "div.TRS_Editor", "article"),
    "www.nc.sgcc.com.cn": ("div.article-content", "div.content", "div.TRS_Editor", "article"),
}
_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "form", "iframe", "noscript")
MIN_TEXT_LEN = 120
_BLOCK_MARKERS = ("请进行验证", "访问验证", "人机验证", "安全检查", "please enable javascript",
                  "access denied", "403 forbidden")


@dataclass
class FullText:
    text: str
    html: str | None


def selectors_for(url: str, extra: list[str] | None = None) -> tuple[str, ...]:
    host = (urlsplit(url).hostname or "").lower()
    return tuple(extra or ()) + DOMAIN_SELECTORS.get(host, ())


def extract_main(html: str, selectors: tuple[str, ...]) -> FullText | None:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    node = next((n for s in selectors if (n := soup.select_one(s)) is not None), None)
    if node is None:
        # 选择器全落空（站点改版）时退回「最长文本块」
        node = max(soup.find_all(["article", "div"]), key=lambda d: len(d.get_text(strip=True)), default=None)
    if node is None:
        return None
    text = clean_text(node.get_text(" ", strip=True))
    low = text.casefold()
    if len(text) < MIN_TEXT_LEN or any(m in low for m in _BLOCK_MARKERS):
        return None
    return FullText(text=text[:12000], html=sanitize_html(str(node)) or None)


async def fetch_fulltext(client: PoliteClient, url: str, extra_selectors: list[str] | None = None) -> FullText | None:
    selectors = selectors_for(url, extra_selectors)
    if not selectors:
        return None  # 只回捞白名单域名，避免把反爬页/登录页当正文入库
    try:
        page = await client.get(url)
    except FetchError:
        return None
    return extract_main(page.text, selectors)
