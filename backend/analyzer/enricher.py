"""阶段②'内容富化（富化链，与评分链并行；aihot v10 的第 7 步「翻译」扩展版）。

单一职责：翻译标题 + 中文摘要 + 标签 + 机构名。不打分、不分类。
与评分链互不依赖，并行执行；任一链失败不拖累另一条。
无 Key 或输出异常时退化为原文透传。
"""
from __future__ import annotations

from analyzer.base import get_analyzer
from analyzer.utils import extract_json

SYSTEM = (
    "你是电力/AI 情报编辑。对给定情报做内容整理，不要评价打分。"
    "严格返回 JSON（不要多余文字）："
    '{"title_zh": "中文标题译文，原文已是中文则填空字符串", '
    '"summary": "不超过100字的中文摘要，提炼实质信息", '
    '"tags": ["2-4个标签，含来源机构与内容类型"], '
    '"org": "来源机构名，如 国家电网/OpenAI/arXiv，未知填 行业"}'
)


def _rule_based(title: str) -> dict:
    return {"title_zh": "", "summary": title, "tags": [], "org": "行业"}


def enrich(title: str, content: str = "", *, provider: str | None = None) -> dict:
    """返回 {title_zh, summary, tags, org}。"""
    analyzer = get_analyzer(provider, task="scorer")  # 与评分同档模型，成本可在 .env 分开调
    body = f"标题：{title}"
    if content:
        body += f"\n正文/摘要（截断）：{content[:600]}"
    raw = analyzer.complete(SYSTEM, body, max_tokens=400)

    data = extract_json(raw)
    if not data or "stub]" in raw:
        return _rule_based(title)
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
    return {
        "title_zh": (data.get("title_zh") or "").strip(),
        "summary": (data.get("summary") or title).strip(),
        "tags": tags[:4],
        "org": (data.get("org") or "行业").strip(),
    }
