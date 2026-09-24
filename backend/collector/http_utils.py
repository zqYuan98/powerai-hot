"""Small helpers shared by HTTP collectors."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 aihot-fansai/0.1.0"
)


def canonical_url(url: str) -> str:
    parsed = urlsplit((url or "").strip())
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", query, ""))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        from email.utils import parsedate_to_datetime

        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_json_response(headers: dict) -> bool:
    return "json" in (headers.get("content-type") or "").lower()


def is_feed_response(headers: dict) -> bool:
    content_type = (headers.get("content-type") or "").lower()
    return any(part in content_type for part in ("xml", "atom", "rss", "text/plain"))
