"""运行时可变配置与调用量统计（进程内）。

生产环境应持久化到数据库/Redis；此处用进程内单例，便于脚手架直接演示
管理后台的「模型切换」与「调用量监控」。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.config import settings

_VALID_PROVIDERS = ("deepseek", "custom", "ollama")


@dataclass
class _Usage:
    calls: int = 0
    tokens: int = 0


@dataclass
class _Runtime:
    provider: str = settings.ai_provider
    # 各任务可独立配置模型：summarizer / tagger
    task_providers: dict[str, str] = field(default_factory=dict)
    usage: dict[str, _Usage] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_provider(self, provider: str) -> None:
        provider = provider.lower()
        if provider not in _VALID_PROVIDERS:
            raise ValueError(f"unknown provider: {provider!r}")
        with self._lock:
            self.provider = provider

    def resolve(self, task: str | None = None) -> str:
        if task and task in self.task_providers:
            return self.task_providers[task]
        return self.provider

    def record(self, provider: str, tokens: int = 0) -> None:
        with self._lock:
            u = self.usage.setdefault(provider, _Usage())
            u.calls += 1
            u.tokens += tokens

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "provider": self.provider,
                "valid_providers": list(_VALID_PROVIDERS),
                "task_providers": dict(self.task_providers),
                "usage": {k: {"calls": v.calls, "tokens": v.tokens} for k, v in self.usage.items()},
            }


runtime = _Runtime()
