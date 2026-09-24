"""阶段①预筛+快速分类（成本闸门，aihot v10 流水线的第 2 步）：

便宜模型一次做两件事：判断是否与电力/AI 相关 + 给出频道篮子标签。
「是不是相关」只在这里判断一次，后续评分不再重复决策；
无关内容直接落库不评分（原因记入 noise_reason，噪音视图可回溯）。
无 Key 或模型输出异常时退化为关键词规则。
"""
from __future__ import annotations

from analyzer.base import get_analyzer
from analyzer.utils import extract_json
from core.constants import CHANNELS

POWER_KW = ["电力", "电网", "变电", "输电", "配电", "特高压", "能源", "招标",
            "布控球", "巡检", "储能", "发电", "输变电"]
AI_KW = ["AI", "人工智能", "大模型", "LLM", "OCR", "视觉", "检测", "识别", "多模态",
         "GPT", "模型", "神经网络", "深度学习", "transformer", "diffusion", "agent",
         "vision", "detection", "recognition", "language model"]

# 硬噪音词（借鉴 ai-news-aggregator 的 noise/commerce 词表）：泛媒体公众号源里
# 混进的电商促销/娱乐八卦，标题特征确定，无需模型判断。
NOISE_KW = ["娱乐", "明星", "八卦", "彩票", "星座", "情感", "旅游攻略", "美食",
            "淘宝", "天猫", "京东", "拼多多", "券后", "促销", "优惠券", "补贴价",
            "下单", "首发价", "热销总榜", "双11", "双十一", "618大促"]


def _hard_noise(title: str) -> bool:
    """命中噪音词且无任何电力/AI 信号 → 确定性无关，直接打回不花模型钱。
    有电力/AI 词时不拦（如「京东云发布电力大模型」），交给模型细判。"""
    if not any(k in title for k in NOISE_KW):
        return False
    low = title.lower()
    return not any(k in title for k in POWER_KW) and not any(k.lower() in low for k in AI_KW)

SYSTEM = (
    "你是情报预筛闸门，判断给定情报是否与「电力/能源行业」或「AI 技术」相关，并给频道分类。"
    "AI 技术的范围要宽：大模型/LLM、机器学习、深度学习、计算机视觉、OCR、多模态、Agent、"
    "AI 基础设施与工具（推理/训练框架、开源模型与权重、模型库）、AI 评测基准与学术研究都算相关；"
    "GitHub 仓库名（owner/repo 形式）若像 AI 项目（如 nanoGPT、vllm、ComfyUI）也判相关。"
    "无关的典型：普通财报人事、消费数码、体育娱乐、与 AI 无关的通用软件工具。"
    "注意：这是低成本粗筛，被误杀的内容会从精选中永远消失，而误放的还有后续精细评分把关——"
    "因此拿不准时一律判 relevant=true。"
    "严格返回 JSON（不要多余文字）："
    '{"relevant": true或false, "domain": "电力"或"AI技术"或"无关", '
    f'"channel": "从{CHANNELS}中选一个"}}'
)


def _rule_channel(title: str) -> str | None:
    """强关键词特征 → 明确频道。这类有确定性特征的分类用代码比模型更准
    （模型倾向把招标/政策都笼统归为行业动态），故规则优先于模型判断。"""
    if any(k in title for k in ["招标", "采购", "中标", "询价", "招投标", "评标",
                                 "中标候选人", "成交公告", "EPC总承包", "公开招标"]):
        return "招标公告"
    if any(k in title for k in ["规划", "十四五", "十五五", "白皮书",
                                 "行动方案", "顶层设计"]):
        return "国网规划"
    if any(k in title for k in ["政策", "发改委", "能源局", "管理办法", "实施方案",
                                 "印发", "征求意见", "监管", "电价", "补贴", "通知"]):
        return "政策法规"
    if any(k in title for k in ["大模型", "LLM", "GPT", "开源模型"]):
        return "大模型动态"
    return None


def _rule_based(title: str) -> dict:
    low = title.lower()
    if any(k in title for k in POWER_KW):
        return {"relevant": True, "domain": "电力", "channel": _rule_channel(title)}
    if any(k.lower() in low for k in AI_KW):
        return {"relevant": True, "domain": "AI技术", "channel": _rule_channel(title)}
    return {"relevant": False, "domain": "无关", "channel": None}


def prefilter(title: str, content: str = "", *, provider: str | None = None) -> dict:
    """返回 {relevant, domain, channel}；channel 为 None 时用采集器默认频道。规则回退只看标题。"""
    # 零成本闸门：电商促销/娱乐八卦类确定性噪音，模型调用之前就打回
    if _hard_noise(title):
        return {"relevant": False, "domain": "无关", "channel": None}
    analyzer = get_analyzer(provider, task="prefilter")
    body = f"标题：{title}"
    if content:
        body += f"\n摘要片段：{content[:200]}"
    raw = analyzer.complete(SYSTEM, body, max_tokens=80)
    data = extract_json(raw)
    if not data or "stub]" in raw or not isinstance(data.get("relevant"), bool):
        return _rule_based(title)
    domain = data.get("domain") if data.get("domain") in ("电力", "AI技术", "无关") else "无关"
    # 强关键词规则优先于模型：招标/政策/规划有确定性特征，代码判定比模型可靠
    channel = _rule_channel(title) or (data.get("channel") if data.get("channel") in CHANNELS else None)
    return {"relevant": bool(data["relevant"]), "domain": domain, "channel": channel}
