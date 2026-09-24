"""北极星电力网采集器 (bjx.com.cn)。

策略：抓频道列表页，从锚文本取标题、从 URL 取日期。中文新闻标题信息量足，
正文页为反爬桩页（GET 取不到内容），故一期按「标题三角洲」做采集，
正文抓取留作后续增强（见 TODO）。
"""
from __future__ import annotations

import re

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

ART_RE = re.compile(r"https?://news\.bjx\.com\.cn/html/(\d{8})/(\d+)\.shtml")

# 子站列表页（均实测静态可抓，文章统一为 news.bjx.com.cn/html/... 格式）。
# 最终频道由预筛按标题判定：招标子站的"招标/中标"标题→招标公告，
# 政策栏目(/zc/)的"政策/规划/通知"标题→政策法规/国网规划，其余→行业动态。
# limit 为「每子站」上限。
CHANNELS = {
    # 招标：原 zhaobiao.bjx.com.cn 于 2026-07 起 HTTPS 握手失败、HTTP 502，已下线。
    # 改用各子站的 /zb/ 招标栏目承接（实测每个 64 条文章链接、招标词密度高）。
    "输配电招标": "https://shupeidian.bjx.com.cn/zb/",
    "储能招标": "https://chuneng.bjx.com.cn/zb/",
    "售电招标": "https://shoudian.bjx.com.cn/zb/",
    "发电招标": "https://fd.bjx.com.cn/zb/",
    "输配电政策": "https://shupeidian.bjx.com.cn/zc/",
    "售电政策": "https://shoudian.bjx.com.cn/zc/",
    "储能政策": "https://chuneng.bjx.com.cn/zc/",
    "输配电网": "https://shupeidian.bjx.com.cn/",
    "储能": "https://chuneng.bjx.com.cn/",
    "电力交易": "https://shoudian.bjx.com.cn/",
    "发电": "https://fd.bjx.com.cn/",
    "北极星主站": "https://www.bjx.com.cn/",
}


class BjxCollector(BaseCollector):
    source_name = "北极星电力网"
    domain = "bjx.com.cn"
    channel = "行业动态"

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit  # 每频道上限

    def fetch(self) -> CollectorResult:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return CollectorResult.parse_error("BeautifulSoup is unavailable")
        out: list[RawArticle] = []
        seen: set[str] = set()
        failures: list[str] = []
        for ch, url in CHANNELS.items():
            try:
                r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
                r.raise_for_status()
            except Exception as exc:
                # 子站逐个记账：招标子站 2026-07 起 SSL 握手失败 + HTTP 502，
                # 旧实现直接 continue，整站健康仍报 ok，招标公告频道断供却无人知晓。
                failures.append(f"{ch}: {type(exc).__name__}")
                continue
            soup = BeautifulSoup(r.text, "lxml")
            taken = 0
            for a in soup.find_all("a", href=True):
                m = ART_RE.match(a["href"])
                if not m:
                    continue
                title = a.get_text(strip=True)
                href = a["href"]
                if not title or len(title) < 8 or href in seen:
                    continue
                seen.add(href)
                d = m.group(1)
                out.append(RawArticle(
                    title=title,
                    url=href,
                    source_domain="bjx.com.cn",
                    published_label=f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                ))
                taken += 1
                if taken >= self.limit:
                    break
        if failures and not out:
            return CollectorResult.network_error("全部子站失败 —— " + "; ".join(failures))
        if failures:
            # 部分子站挂了：有产出但要亮黄，否则「招标断供」会被其他子站的产出掩盖。
            return CollectorResult(items=out, transport_status="ok", parse_status="ok",
                                   error_summary="部分子站失败 —— " + "; ".join(failures))
        return CollectorResult.ok(items=out)
        # TODO: 抓取正文（反爬，需带 Referer/会话或 Playwright），用于更精准的摘要。
