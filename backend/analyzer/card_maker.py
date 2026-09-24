"""知识卡片生成器（writer 角色）：收藏触发，把文章提炼为结构化卡片。

无 Key 或输出异常时走规则回退（分类靠关键词，正文字段留提示语），保证链路可跑通。
"""
from __future__ import annotations

from analyzer.base import get_analyzer
from analyzer.utils import extract_json

CATEGORIES = ["视觉/OCR", "大模型", "电力AI应用", "其他"]

_VISION_KW = ["OCR", "视觉", "检测", "识别", "分割", "document", "vision", "detection",
              "recognition", "segmentation", "图像", "缺陷"]
_LLM_KW = ["大模型", "LLM", "GPT", "多模态", "language model", "agent", "Agent", "开源模型"]
_POWER_KW = ["电力", "电网", "变电", "输电", "特高压", "巡检", "布控球", "国网", "安监"]

SYSTEM = (
    "你是电力基建行业 AI 算法负责人的知识管理助手。用户方向：视觉（目标检测/缺陷识别）、"
    "OCR/文档理解、多模态大模型；业务场景：布控球、无人机巡检、变电站监控、施工安监。"
    "把给定内容提炼为知识卡片，严格返回 JSON（不要多余文字）："
    '{"category": "从[视觉/OCR,大模型,电力AI应用,其他]中选一个", '
    '"problem": "解决什么问题，不超过60字", '
    '"method": "核心方法/机制，不超过100字", '
    '"conclusion": "关键结论/效果，不超过80字", '
    '"power_relevance": "与电力场景（巡检/监控/安监/文档处理）的关联与可借鉴点，不超过80字"}'
)


def _rule_category(text: str) -> str:
    low = text.lower()
    if any(k in text for k in _POWER_KW):
        return "电力AI应用"
    if any(k.lower() in low for k in _VISION_KW):
        return "视觉/OCR"
    if any(k.lower() in low for k in _LLM_KW):
        return "大模型"
    return "其他"


def _rule_based(title: str, summary: str) -> dict:
    return {
        "category": _rule_category(f"{title} {summary}"),
        "problem": summary or title,
        "method": "（未接入生成模型，待补充）",
        "conclusion": "（未接入生成模型，待补充）",
        "power_relevance": "（未接入生成模型，待补充）",
    }


def make_card(title: str, summary: str = "", content: str = "",
              *, provider: str | None = None) -> dict:
    """返回 {category, problem, method, conclusion, power_relevance}。"""
    analyzer = get_analyzer(provider, task="writer")
    body = f"标题：{title}"
    if summary:
        body += f"\n摘要：{summary}"
    if content:
        body += f"\n正文（截断）：{content[:800]}"
    raw = analyzer.complete(SYSTEM, body, max_tokens=500)

    data = extract_json(raw)
    if not data or "stub]" in raw:
        return _rule_based(title, summary)
    return {
        "category": data.get("category") if data.get("category") in CATEGORIES else "其他",
        "problem": (data.get("problem") or "").strip(),
        "method": (data.get("method") or "").strip(),
        "conclusion": (data.get("conclusion") or "").strip(),
        "power_relevance": (data.get("power_relevance") or "").strip(),
    }
