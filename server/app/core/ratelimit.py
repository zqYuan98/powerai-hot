"""进程内滑动窗口限频（API 是单进程，够用）。只用于访客：搜索会调模型、反馈会推送飞书。"""
from __future__ import annotations

import math
import time
from collections import deque

from fastapi import HTTPException, Request


def client_ip(request: Request) -> str:
    # uvicorn 开了 --proxy-headers，这里已是 Caddy 传来的真实地址；Next 服务端取数时会转发 X-Forwarded-For
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window_s: float, message: str = "请求太频繁，请稍后再试") -> None:
        self.limit = limit
        self.window_s = window_s
        self.message = message
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, now: float | None = None) -> None:
        """记一次；超额时抛 429 并带 Retry-After。"""
        now = time.monotonic() if now is None else now
        if len(self._hits) > 10_000:
            self._prune(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            retry = max(1, math.ceil(hits[0] + self.window_s - now))
            raise HTTPException(429, self.message, headers={"Retry-After": str(retry)})
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()

    def _prune(self, now: float) -> None:
        self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - self.window_s}


SEARCH_LIMIT = RateLimiter(20, 60, "搜索太频繁，请一分钟后再试")
FEEDBACK_LIMIT = RateLimiter(5, 600, "提交太频繁，请十分钟后再试")
