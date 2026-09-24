"""模型调用抽象接口 — 不同任务可独立配置模型。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Analyzer(ABC):
    """Common interface every model backend implements."""

    name: str = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, *, max_tokens: int = 512,
                 temperature: float = 0.3) -> str:
        """Return the model's text completion for the given prompt."""
        raise NotImplementedError


def get_analyzer(provider: str | None = None, *, task: str | None = None) -> Analyzer:
    """Factory — resolve a provider name to an Analyzer instance.

    Resolution order: explicit ``provider`` arg → per-task override → the
    runtime-selected provider (switchable from the admin backend) → settings
    default (DeepSeek).
    """
    from analyzer.custom import CustomAnalyzer
    from analyzer.deepseek import DeepSeekAnalyzer
    from core.runtime import runtime

    provider = (provider or runtime.resolve(task)).lower()
    if provider == "custom":
        return CustomAnalyzer()
    if provider == "deepseek":
        from core.config import settings

        model = {
            "prefilter": settings.deepseek_prefilter_model,
            "scorer": settings.deepseek_scorer_model,
            "writer": settings.deepseek_writer_model,
        }.get(task or "")
        return DeepSeekAnalyzer(model=model)
    raise ValueError(f"unknown AI provider: {provider!r}")
