"""礼貌抓取客户端：共享连接池、每域串行 + 最小间隔、中文编码回退。"""
from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
}
_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.IGNORECASE)

FetchErrorKind = Literal["timeout", "http_error", "network_error"]


class FetchError(Exception):
    def __init__(self, kind: FetchErrorKind, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class Page:
    url: str
    status: int
    headers: httpx.Headers
    content: bytes

    @property
    def text(self) -> str:
        return decode_html(self.content, self.headers.get("content-type"))


def decode_html(content: bytes, content_type: str | None = None) -> str:
    """按 header → meta → utf-8 → gb18030 的顺序解码。国内政府/电网站点常见 GBK 未声明。"""
    candidates: list[str] = []
    if content_type and "charset=" in content_type.lower():
        candidates.append(content_type.lower().split("charset=")[-1].split(";")[0].strip())
    if m := _META_CHARSET.search(content[:4096]):
        candidates.append(m.group(1).decode("ascii", "ignore").lower())
    candidates += ["utf-8", "gb18030"]
    for enc in candidates:
        enc = "gb18030" if enc in ("gbk", "gb2312") else enc
        try:
            return content.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


class PoliteClient:
    """对同一域名串行请求并保持最小间隔，避免把政府/电网站点打出风控。"""

    def __init__(
        self,
        *,
        min_interval_s: float = 1.5,
        timeout_s: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.min_interval_s = min_interval_s
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=timeout_s,
            transport=transport,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last: dict[str, float] = {}

    async def __aenter__(self) -> PoliteClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        raise_for_status: bool = True,
    ) -> Page:
        host = (urlsplit(url).hostname or "").lower()
        async with self._locks[host]:
            wait = self._last.get(host, 0.0) + self.min_interval_s - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await self._client.get(url, headers=headers, follow_redirects=follow_redirects)
            except httpx.TimeoutException as exc:
                raise FetchError("timeout", f"{host} 请求超时") from exc
            except httpx.HTTPError as exc:
                raise FetchError("network_error", f"{host} {type(exc).__name__}: {exc}"[:300]) from exc
            finally:
                self._last[host] = time.monotonic()
        if raise_for_status and resp.status_code >= 400:
            raise FetchError("http_error", f"{host} HTTP {resp.status_code}", resp.status_code)
        return Page(url=str(resp.url), status=resp.status_code, headers=resp.headers, content=resp.content)
