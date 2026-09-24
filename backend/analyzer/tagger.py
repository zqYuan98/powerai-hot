"""自动打标签（调用配置模型）。"""
from analyzer.base import get_analyzer

SYSTEM = (
    "你是电力行业内容标注助手。请为文章输出 2-4 个简短中文标签，"
    "覆盖来源机构与内容类型（如：国家电网、行业动态、招标公告、特高压、布控球）。"
    "仅返回以逗号分隔的标签。"
)


def tag(text: str, *, provider: str | None = None) -> list[str]:
    analyzer = get_analyzer(provider, task="tagger")
    raw = analyzer.complete(SYSTEM, text, max_tokens=64)
    return [t.strip() for t in raw.replace("，", ",").split(",") if t.strip()][:4]
