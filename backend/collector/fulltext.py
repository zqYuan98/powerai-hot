"""正文回捞：为只有标题的条目补抓详情页正文。

背景：电力侧采集器（bjx / nea / sgcc / csg / 政采 / 南网供应链）都只从列表页
取标题，`content` 一律为空。实测生产库里 297 条非噪音条目无正文，其中
北极星 180、南网供应链 48、政采 25、能源局 18、南网 14、国网 12。

后果不在评分（实测有无正文的维度分差异不大），而在两处：
  - `enricher` 只见标题 → summary 退化成标题复读，卡片没有信息量
  - 招标类内容的 depth 被压到 30 左右，模型的 reason 会明说「仅为招标标题，缺少技术细节」

**已知限制**：`news.bjx.com.cn` 是 JS 反爬（返回「为了更好的访问体验，请进行验证」），
纯 HTTP 拿不到正文，实测加 Referer、完整浏览器头、先访问列表页拿 cookie 均无效。
要覆盖它需要引入 Playwright，对 3.6 GiB 的生产机是笔不小的开销，故本模块暂不覆盖
bjx —— 它的 180 条仍是标题级。这是有意的取舍，不是遗漏。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from core.htmlsanitize import sanitize_html

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 只回捞白名单域名：实测可拿到正文的站点。未列入的域名直接跳过，
# 避免对任意外链发起请求（既是礼貌，也避免把反爬页/登录页当正文入库）。
SUPPORTED_DOMAINS: dict[str, tuple[str, ...]] = {
    # 域名 → 候选正文容器选择器，按优先级排列
    # 选择器实测自真实详情页（2026-07-26），按「最贴正文」优先
    "www.csg.cn": ("#ArtText", "div.TRS_Editor", "#articleText", "div.con-right"),
    "bidding.csg.cn": ("div.Content", "div.Section0", "div.s-content"),
    "www.bidding.csg.cn": ("div.Content", "div.Section0", "div.s-content"),
    "www.ccgp.gov.cn": ("div.vF_detail_content", "div.vF_deail_maincontent"),
    "www.nea.gov.cn": ("div.article-content", "div.content", "div.TRS_Editor", "article"),
    "www.nc.sgcc.com.cn": ("div.article-content", "div.content", "div.TRS_Editor", "article"),
}

# 去掉的结构性噪音标签
_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "form", "iframe", "noscript")

# 正文有效性下限：低于此长度视为没抓到（多半是反爬页或空壳）
MIN_TEXT_LEN = 120

# 反爬/占位页特征，命中即判失败
_BLOCK_MARKERS = (
    "请进行验证", "访问验证", "人机验证", "安全检查",
    "please enable javascript", "access denied", "403 forbidden",
)


def domain_of(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").lower() or None
    except ValueError:
        return None


def is_supported(url: str | None) -> bool:
    """该 URL 是否在回捞白名单内。"""
    if not url:
        return False
    return domain_of(url) in SUPPORTED_DOMAINS


def _looks_blocked(text: str) -> bool:
    low = text.casefold()
    return any(marker.casefold() in low for marker in _BLOCK_MARKERS)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fetch_fulltext(url: str, *, timeout: float = 15.0) -> dict | None:
    """回捞正文。

    返回 ``{"content": 纯文本, "content_html": 消毒后的富文本, "chars": n}``；
    抓不到或疑似反爬页时返回 ``None``（调用方保持原样，不写脏数据）。
    """
    host = domain_of(url)
    selectors = SUPPORTED_DOMAINS.get(host or "")
    if not selectors:
        return None
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None

    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    node = None
    for selector in selectors:
        node = soup.select_one(selector)
        if node is not None:
            break
    if node is None:
        # 选择器全落空时退回「最长文本块」，站点改版也还能出内容
        candidates = soup.find_all(["article", "div"])
        node = max(candidates, key=lambda d: len(d.get_text(strip=True)), default=None)
    if node is None:
        return None

    text = _clean_text(node.get_text(" ", strip=True))
    if len(text) < MIN_TEXT_LEN or _looks_blocked(text):
        return None
    return {
        "content": text[:8000],
        "content_html": sanitize_html(str(node)) or None,
        "chars": len(text),
    }
