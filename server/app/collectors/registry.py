"""信源 → 采集器的装配。kind 决定实现；custom 类按 source.key 查专用实现。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.collectors.base import Collector
from app.collectors.html_list import HtmlListCollector, HtmlListConfig
from app.collectors.rss import RssCollector
from app.models.enums import SourceKind

# 需要专门代码的站点（接口型/SPA）：key → 工厂(config) -> Collector
CUSTOM: dict[str, Callable[[dict[str, Any]], Collector]] = {}


def register(key: str) -> Callable[[Callable[[dict[str, Any]], Collector]], Callable[[dict[str, Any]], Collector]]:
    def deco(factory: Callable[[dict[str, Any]], Collector]) -> Callable[[dict[str, Any]], Collector]:
        CUSTOM[key] = factory
        return factory
    return deco


class UnknownCollector(LookupError):
    pass


def build_collector(key: str, kind: str, url: str, config: dict[str, Any]) -> Collector:
    if kind == SourceKind.HTML_LIST:
        return HtmlListCollector(HtmlListConfig.model_validate(config))
    if kind == SourceKind.RSS:
        return RssCollector(url, limit=int(config.get("limit", 30)))
    if kind == SourceKind.CUSTOM and key in CUSTOM:
        return CUSTOM[key](config)
    raise UnknownCollector(f"信源 {key} 没有可用的采集器（kind={kind}）")
