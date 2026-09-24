"""阶段②六维评分（评分链，与富化链并行；aihot v10 的第 4 步）。

六维分两组职责：ai_relevance / power_relevance 是**定位**（合成 cross_score 与
axis），firsthand / utility / impact / depth 是**质量**（合成 quality）。两组正交
——「非常对口但质量一般」和「质量很高但不相关」必须能分别表达。

单一职责：模型只打六个维度分（0-100）+ 一句话推荐理由，不打总分、
不做翻译/摘要/分类（分类在预筛，内容富化在 enricher）——评判与生成
分离后打分更客观，任一环失败互不拖累。总分由 analyzer/scoring.py 纯代码合成。
低温采样（0.1）保证打分稳定。无 Key 或输出异常时退化为关键词规则。
"""
from __future__ import annotations

from analyzer.base import get_analyzer
from analyzer.scoring import DIM_KEYS
from analyzer.utils import extract_json

# 用户画像：评分提示词的核心。业务关键词沿用原 curator 的口径。
BIZ_KEYWORDS = [
    "布控球", "边缘AI", "边缘计算", "智能巡检", "无人机", "视频监控", "安全帽",
    "违章", "变电站", "智能终端", "AI识别", "感知终端", "人工智能", "智能监测",
    "OCR", "文档理解", "目标检测", "缺陷", "多模态",
]

SYSTEM = (
    "你是电力基建行业 AI 算法负责人的私人情报评审。用户画像：电力基建集成商的算法负责人，"
    "技术方向为视觉（目标检测/缺陷识别）、OCR/文档理解、多模态大模型、边缘部署；"
    "业务场景为布控球、无人机巡检、变电站监控、施工安监。"
    "只做评审，不做翻译摘要。"
    "关键：相关度拆成互相独立的两轴，分别打分，不要互相牵制。"
    "**按内容讲的是什么打分，不要按文档体裁打分**——"
    "「招标公告」「政策文件」只是体裁，要看它采购/规范的对象是什么："
    "「变电站智能传感终端采购」采购的是 AI 感知设备，AI 轴就该高（≥60）；"
    "「红外监测及巡检机器人采购」同理；"
    "「常年法律顾问框架采购」才是与 AI 无关的招标（AI 轴 <20）。"
    "两轴都高的（如「电网无人机巡检缺陷识别模型上线」「人工智能与能源电力双向赋能」"
    "「数字变电站智能配电传感终端招标」）是最有价值的情报，不要因为它是招标/政策就压低 AI 轴。"
    "对给定情报严格返回 JSON（不要多余文字）："
    '{"dims": {"firsthand": "0-100，一手性：官方发布/原始论文高，二手转述低", '
    '"ai_relevance": "0-100，AI 技术轴：内容涉及视觉/检测/识别/OCR/文档理解/多模态/'
    '智能终端/边缘计算/算法/大模型的程度。涉及智能感知设备、监测识别系统、机器人、'
    '数字化平台的采购或规划同样算高；完全不涉及智能技术的（法律服务、土建、人事）才低于 20", '
    '"power_relevance": "0-100，电力业务轴：与电网规划、输变电基建、设备运检、施工安监、'
    '电力市场交易、电力招标采购的相关度。与电力能源行业无关的内容（通用 AI 模型发布、'
    '消费电子、通用软件）应低于 20", '
    '"utility": "0-100，工程实用性：有代码/可落地方法/工程细节高", '
    '"impact": "0-100，行业影响力", '
    '"depth": "0-100，内容深度：实质信息量高，营销口水低"}, '
    '"reason": "一句话推荐理由，说明为什么值得该用户关注"}'
)


def _clamp(v) -> int:
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return 0


AI_AXIS_KW = ["AI", "人工智能", "大模型", "LLM", "OCR", "视觉", "检测", "识别", "多模态",
              "算法", "模型", "深度学习", "神经网络", "推理", "训练", "边缘计算", "量化"]
POWER_AXIS_KW = ["电力", "电网", "变电", "输电", "配电", "特高压", "能源", "发电", "储能",
                 "招标", "中标", "采购", "巡检", "安监", "基建", "运检", "电价", "国网", "南网"]


def _axis_hits(title: str, keywords: list[str]) -> int:
    low = title.lower()
    return sum(1 for k in keywords if k in title or k.lower() in low)


def _rule_based(title: str) -> dict:
    hits = [k for k in BIZ_KEYWORDS if k in title]
    return {
        "dims": {
            "firsthand": 50,
            "ai_relevance": min(15 + 20 * _axis_hits(title, AI_AXIS_KW), 90),
            "power_relevance": min(15 + 20 * _axis_hits(title, POWER_AXIS_KW), 90),
            "utility": 40,
            "impact": 45,
            "depth": 40,
        },
        "reason": f"命中关键词：{'、'.join(hits[:3])}" if hits else "规则回退，未接入评分模型。",
        # 调用方据此区分「模型真打了分」与「静默降级成关键词估分」。
        # 不加这个标记就只能靠 reason 文案反推——回填脚本曾因此把 58% 的规则分
        # 当成模型分写进库，且完全无感。
        "fallback": True,
    }


def score(title: str, content: str = "", *, provider: str | None = None) -> dict:
    """返回 {dims, reason, fallback}；fallback=True 表示模型不可用、已退回关键词估分。"""
    analyzer = get_analyzer(provider, task="scorer")
    body = f"标题：{title}"
    if content:
        body += f"\n正文/摘要（截断）：{content[:600]}"
    # 800 而非 300：deepseek-v4 系列是推理模型，思维链与正式回复共用 max_tokens。
    # 预算太紧会出现「HTTP 200 但 content 为空、内容全在 reasoning_content」，
    # 于是 extract_json 失败、静默退回关键词规则——2026-07-25 回填有 58% 因此变成规则分。
    raw = analyzer.complete(SYSTEM, body, max_tokens=800, temperature=0.1)

    data = extract_json(raw)
    if not data or "stub]" in raw or not isinstance(data.get("dims"), dict):
        return _rule_based(title)
    return {
        "dims": {k: _clamp(data["dims"].get(k)) for k in DIM_KEYS},
        "reason": (data.get("reason") or "").strip(),
        "fallback": False,
    }
