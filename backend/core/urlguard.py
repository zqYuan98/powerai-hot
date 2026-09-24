"""信源 URL 安全校验（防 SSRF / 本地文件读取）。

feedparser.parse 会服务端发起请求，且支持 file:// 与内网地址——提报入库前
必须把 URL 收窄到 http/https 且非环回/私网地址。这是代理式抓取的信任边界。
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")


def _is_blocked_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return True  # 无法解析：保守拒绝
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return True
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return True
    return False


def is_safe_scheme(url: str) -> bool:
    """免 DNS 的廉价检查：仅 http/https 且有主机名。拦住 file:// 等本地协议读取。"""
    parsed = urlparse((url or "").strip())
    return parsed.scheme.lower() in _ALLOWED_SCHEMES and bool(parsed.hostname)


def validate_feed_url(url: str) -> None:
    """完整校验（提报入口用）：scheme + 私网/环回黑名单。抛 ValueError 供 API 转 400。"""
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError("信源 URL 只允许 http/https（禁止 file:// 等本地协议）")
    if not parsed.hostname:
        raise ValueError("信源 URL 缺少主机名")
    if _is_blocked_ip(parsed.hostname):
        raise ValueError("信源 URL 指向内网/环回地址，已拒绝")
