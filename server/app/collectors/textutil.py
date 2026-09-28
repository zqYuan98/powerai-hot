"""采集用文本工具：URL 规范化、日期解析（含中文相对时间）。"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")
_TRACKING_PREFIXES = ("utm_", "spm", "from", "share")

_ABS_PATTERNS = (
    re.compile(r"(?P<y>20\d{2})\s*[-/.年]\s*(?P<m>\d{1,2})\s*[-/.月]\s*(?P<d>\d{1,2})\s*日?"
               r"(?:\s+(?P<H>\d{1,2}):(?P<M>\d{2}))?"),
    re.compile(r"(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})"),
)
_REL_MIN = re.compile(r"(\d+)\s*分钟前")
_REL_HOUR = re.compile(r"(\d+)\s*小时前")
_REL_DAY = re.compile(r"(\d+)\s*天前")
_YESTERDAY = re.compile(r"昨天\s*(?:(\d{1,2}):(\d{2}))?")
_TODAY = re.compile(r"今天\s*(?:(\d{1,2}):(\d{2}))?")


def canonical_url(url: str) -> str:
    """去掉跟踪参数与片段，主机名小写。用于去重，不用于展示。"""
    parts = urlsplit(url.strip())
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not k.lower().startswith(_TRACKING_PREFIXES)]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def cn_date(y: int, m: int, d: int, hour: int = 0, minute: int = 0) -> datetime | None:
    """中国站点给的日期按北京时间理解，再转 UTC 存储。"""
    try:
        return datetime(y, m, d, hour, minute, tzinfo=CN_TZ).astimezone(UTC)
    except ValueError:
        return None


def date_from_groups(groups: dict[str, str | None]) -> datetime | None:
    """从链接正则的命名分组（y/m/d，d 可缺省）取日期。"""
    y, m = groups.get("y"), groups.get("m")
    if not (y and m):
        return None
    return cn_date(int(y), int(m), int(groups.get("d") or 1))


def parse_cn_datetime(text: str | None, *, now: datetime | None = None) -> datetime | None:
    """解析「2026-09-28」「2026年9月28日 10:30」「3小时前」「昨天 08:15」等。"""
    if not text:
        return None
    s = text.strip()
    now_cn = (now or datetime.now(UTC)).astimezone(CN_TZ)
    for pattern in _ABS_PATTERNS:
        if m := pattern.search(s):
            g = m.groupdict()
            return cn_date(int(g["y"]), int(g["m"]), int(g["d"]), int(g.get("H") or 0), int(g.get("M") or 0))
    if m := _REL_MIN.search(s):
        return (now_cn - timedelta(minutes=int(m.group(1)))).astimezone(UTC)
    if m := _REL_HOUR.search(s):
        return (now_cn - timedelta(hours=int(m.group(1)))).astimezone(UTC)
    if m := _REL_DAY.search(s):
        return (now_cn - timedelta(days=int(m.group(1)))).astimezone(UTC)
    for pattern, delta in ((_YESTERDAY, 1), (_TODAY, 0)):
        if m := pattern.search(s):
            day = now_cn - timedelta(days=delta)
            hour, minute = int(m.group(1) or 0), int(m.group(2) or 0)
            return day.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(UTC)
    return None
