"""信源 URL 安全校验（防 SSRF）：仅 http/https，且解析后不落在内网/环回地址。"""
from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import urlsplit


class UnsafeUrl(ValueError):
    pass


async def validate_public_url(url: str) -> None:
    parts = urlsplit((url or "").strip())
    if parts.scheme.lower() not in ("http", "https"):
        raise UnsafeUrl("只允许 http/https")
    if not parts.hostname:
        raise UnsafeUrl("缺少主机名")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, None)
    except OSError as exc:
        raise UnsafeUrl(f"无法解析主机 {parts.hostname}") from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
                or addr.is_multicast or addr.is_unspecified):
            raise UnsafeUrl("指向内网/环回地址，已拒绝")
