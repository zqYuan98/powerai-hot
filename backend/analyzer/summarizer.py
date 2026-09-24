"""摘要生成（调用配置模型）。"""
from analyzer.base import get_analyzer

SYSTEM = (
    "你是电力基建行业的情报分析助手。请用不超过 100 字的中文摘要提炼文章关键信息，"
    "突出与布控球、无人机巡检、边缘 AI 等智能终端采购相关的要点。"
)


def summarize(text: str, *, provider: str | None = None) -> str:
    analyzer = get_analyzer(provider, task="summarizer")
    return analyzer.complete(SYSTEM, text, max_tokens=256)
