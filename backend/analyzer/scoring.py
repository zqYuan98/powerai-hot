"""纯代码评分 —— 模型只出维度分，总分/精选/双轴判定全部在这里（零 LLM）。

aihot 作者的核心教训：能用代码处理的一律不用模型。权重/系数/阈值可配置，
改配置后可对全库已存的维度分瞬间重算（见 services/config_store.py）。

双轴设计（2026-07-25）：
原来只有一个 relevance 维度，画像是单极的「AI 算法负责人」，导致纯电力政策/招标
内容的相关度天然低分，行业侧内容被评分器主动筛掉——这正是产品「四不像」的成因。
现在拆成 ai_relevance（AI 技术轴）与 power_relevance（电力业务轴）两个独立维度：

  quality      = 六维加权均值 × tier系数 × kind系数   —— 「内容本身好不好」
  cross_score  = √(ai × power)                        —— 「落不落在交叉区」
  axis         = 交叉 / AI / 行业 / 弱                 —— 三条流的分派依据

用几何平均而不是算术平均：算术平均下「AI 100 + 电力 0」= 50，仍会被当成半相关，
几何平均下等于 0——只有两轴都不低才可能高，这才是「交叉」的语义。
"""
from __future__ import annotations

from math import sqrt

from core.constants import CHANNELS

DIM_KEYS = ("firsthand", "ai_relevance", "power_relevance", "utility", "impact", "depth")

# 轴标签（同时用于前端筛选与监控分组）
AXIS_CROSS = "交叉"
AXIS_AI = "AI"
AXIS_POWER = "行业"
AXIS_WEAK = "弱"
AXES = (AXIS_CROSS, AXIS_AI, AXIS_POWER, AXIS_WEAK)

DEFAULT_CONFIG: dict = {
    # 六维权重：两轴相关度合计 40，与原 relevance 的 30 相当且略有提升
    "dim_weights": {
        "ai_relevance": 20,
        "power_relevance": 20,
        "firsthand": 20,
        "utility": 20,
        "impact": 10,
        "depth": 10,
    },
    # tier 影响排序而非一票否决（2026-07-25 实测：旧值 T2=0.7 使 T2 通过数恒为 0）
    "tier_coeff": {"T1": 1.0, "T1.5": 0.92, "T2": 0.85},
    "kind_coeff": {"资讯": 1.0, "论文": 1.0, "案例": 1.0},
    "channel_thresholds": {ch: 60 for ch in CHANNELS},
    # 某一轴达到多少算「高」，决定 axis 分类
    "axis_threshold": 45,
    # 识别高价值交叉内容所需的 cross_score；只做属性标识，不绕过精选门槛
    "cross_threshold": 50,
    # 交叉候选的质量下限，避免极差内容被标成高价值交叉候选
    "cross_quality_floor": 35,
    "hot_score": 80,
    "cluster_threshold": 0.82,
}


def _dim(dims: dict, key: str) -> float:
    """读取单个维度并 clamp 到 [0,100]；缺失或非数值按 0 处理。"""
    try:
        return max(0.0, min(100.0, float(dims.get(key, 0) or 0)))
    except (TypeError, ValueError):
        return 0.0


def compute_quality(dims: dict, tier: str, kind: str, config: dict | None = None) -> int:
    """quality = 加权维度均值 × tier系数 × kind系数，clamp 到 [0,100]。"""
    cfg = config or DEFAULT_CONFIG
    weights: dict = cfg["dim_weights"]
    total_w = sum(weights.values()) or 1
    base = sum(_dim(dims, k) * w for k, w in weights.items()) / total_w
    tier_c = cfg["tier_coeff"].get(tier, cfg["tier_coeff"].get("T2", 0.85))
    kind_c = cfg["kind_coeff"].get(kind, 1.0)
    return max(0, min(100, round(base * tier_c * kind_c)))


def compute_cross_score(dims: dict, config: dict | None = None) -> int:
    """两轴的几何平均：只有 AI 与电力都不低时才高。

    不乘 tier 系数 —— cross_score 衡量的是「这条内容落不落在交叉区」，
    是内容属性，与信源权威性无关；权威性已经体现在 quality 里了。
    """
    ai = _dim(dims, "ai_relevance")
    power = _dim(dims, "power_relevance")
    return max(0, min(100, round(sqrt(ai * power))))


def classify_axis(dims: dict, config: dict | None = None) -> str:
    """按两轴分派到三条流：交叉 / AI 技术 / 行业动态 / 弱相关。"""
    cfg = config or DEFAULT_CONFIG
    threshold = cfg.get("axis_threshold", DEFAULT_CONFIG["axis_threshold"])
    ai_high = _dim(dims, "ai_relevance") >= threshold
    power_high = _dim(dims, "power_relevance") >= threshold
    if ai_high and power_high:
        return AXIS_CROSS
    if ai_high:
        return AXIS_AI
    if power_high:
        return AXIS_POWER
    return AXIS_WEAK


def is_curated(quality: int, channel: str, config: dict | None = None) -> bool:
    cfg = config or DEFAULT_CONFIG
    return quality >= cfg["channel_thresholds"].get(channel, 60)


def is_cross_pick(cross_score: int, quality: int, axis: str, config: dict | None = None) -> bool:
    """识别交叉候选；该信号只用于交叉区标识和排序，不等于推荐。"""
    cfg = config or DEFAULT_CONFIG
    if axis != AXIS_CROSS:
        return False
    return (
        cross_score >= cfg.get("cross_threshold", DEFAULT_CONFIG["cross_threshold"])
        and quality >= cfg.get("cross_quality_floor", DEFAULT_CONFIG["cross_quality_floor"])
    )


def evaluate(dims: dict, *, tier: str, kind: str, channel: str, config: dict | None = None) -> dict:
    """一次算全所有派生分。

    ingest 的两条链路和 config_store 的全库重算都走这里，避免三处各写一遍
    导致口径漂移（改配置后重算的结果必须和入库时一致，否则精选会莫名其妙地跳变）。

    职责分离：axis / cross_score 描述「这条内容是什么」，是内容属性，任何链路都要算；
    curated 描述「要不要推荐」，沿用各链路既有的门槛机制（频道阈值或研究方向阈值）。
    「交叉精选」= curated AND axis == 交叉，在查询层组合，不在这里硬编码——
    否则会和 services/ingest.py 的研究方向阈值形成两套互相打架的精选口径。
    """
    cfg = config or DEFAULT_CONFIG
    quality = compute_quality(dims, tier, kind, cfg)
    cross = compute_cross_score(dims, cfg)
    axis = classify_axis(dims, cfg)
    return {
        "quality": quality,
        "cross_score": cross,
        "axis": axis,
        # 推荐必须通过频道质量门槛；交叉属性不能绕过推荐门槛
        "curated": is_curated(quality, channel, cfg),
        "cross_pick": is_cross_pick(cross, quality, axis, cfg),
        "hot": quality >= cfg["hot_score"],
    }
