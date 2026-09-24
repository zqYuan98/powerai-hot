from analyzer.scoring import (
    AXIS_AI,
    AXIS_CROSS,
    AXIS_POWER,
    AXIS_WEAK,
    DEFAULT_CONFIG,
    classify_axis,
    compute_cross_score,
    compute_quality,
    evaluate,
    is_curated,
)

DIMS_FULL = {"firsthand": 100, "ai_relevance": 100, "power_relevance": 100,
             "utility": 100, "impact": 100, "depth": 100}
# 加权均值：(80*20 + 90*20 + 40*20 + 60*20 + 50*10 + 70*10)/100 = 66
DIMS_MIXED = {"firsthand": 80, "ai_relevance": 90, "power_relevance": 40,
              "utility": 60, "impact": 50, "depth": 70}


def test_full_dims_t1_gives_100():
    assert compute_quality(DIMS_FULL, "T1", "资讯") == 100


def test_tier_coefficient_applied():
    q1 = compute_quality(DIMS_MIXED, "T1", "资讯")
    q2 = compute_quality(DIMS_MIXED, "T2", "资讯")
    assert q2 < q1
    assert q1 == 66
    assert q2 == round(66 * DEFAULT_CONFIG["tier_coeff"]["T2"])


def test_unknown_tier_falls_back_to_t2():
    assert compute_quality(DIMS_MIXED, "T9", "资讯") == compute_quality(DIMS_MIXED, "T2", "资讯")


def test_missing_dim_counts_as_zero():
    q = compute_quality({"ai_relevance": 100}, "T1", "资讯")
    assert q == 20  # 只有 ai_relevance（权重 20）有分


def test_clamped_0_100():
    assert compute_quality({k: 999 for k in DIMS_FULL}, "T1", "资讯") == 100
    assert compute_quality({}, "T1", "资讯") == 0


def test_custom_config_weights():
    cfg = {**DEFAULT_CONFIG, "dim_weights": {"ai_relevance": 100}}
    assert compute_quality(DIMS_MIXED, "T1", "资讯", cfg) == 90


def test_is_curated_threshold_per_channel():
    cfg = {**DEFAULT_CONFIG, "channel_thresholds": {**DEFAULT_CONFIG["channel_thresholds"], "前沿论文": 70}}
    assert is_curated(69, "前沿论文", cfg) is False
    assert is_curated(70, "前沿论文", cfg) is True
    assert is_curated(60, "行业动态", cfg) is True


def test_unknown_channel_uses_60():
    assert is_curated(60, "不存在的频道") is True
    assert is_curated(59, "不存在的频道") is False


# —— 双轴 ——

def test_cross_score_is_geometric_mean():
    assert compute_cross_score({"ai_relevance": 100, "power_relevance": 100}) == 100
    assert compute_cross_score({"ai_relevance": 64, "power_relevance": 36}) == 48


def test_cross_score_collapses_when_one_axis_is_zero():
    """关键性质：单轴再高，只要另一轴为 0，交叉分就是 0。

    这正是几何平均相对算术平均的价值——算术平均下「AI 100 + 电力 0」= 50，
    纯 AI 内容会被误当成半相关塞进精选，那就退回单轴时代了。
    """
    assert compute_cross_score({"ai_relevance": 100, "power_relevance": 0}) == 0
    assert compute_cross_score({"ai_relevance": 0, "power_relevance": 100}) == 0


def test_classify_axis_four_way():
    assert classify_axis({"ai_relevance": 80, "power_relevance": 80}) == AXIS_CROSS
    assert classify_axis({"ai_relevance": 80, "power_relevance": 10}) == AXIS_AI
    assert classify_axis({"ai_relevance": 10, "power_relevance": 80}) == AXIS_POWER
    assert classify_axis({"ai_relevance": 10, "power_relevance": 10}) == AXIS_WEAK


def test_axis_threshold_configurable():
    dims = {"ai_relevance": 50, "power_relevance": 50}
    assert classify_axis(dims, {**DEFAULT_CONFIG, "axis_threshold": 40}) == AXIS_CROSS
    assert classify_axis(dims, {**DEFAULT_CONFIG, "axis_threshold": 60}) == AXIS_WEAK


def test_evaluate_bundles_all_derived_scores():
    verdict = evaluate(DIMS_FULL, tier="T1", kind="资讯", channel="行业动态")
    assert verdict["quality"] == 100
    assert verdict["cross_score"] == 100
    assert verdict["axis"] == AXIS_CROSS
    assert verdict["curated"] is True
    assert verdict["hot"] is True


def test_evaluate_pure_ai_content_is_not_cross():
    """纯 AI 内容：质量可以高，但不该被标成交叉。"""
    dims = {"firsthand": 95, "ai_relevance": 90, "power_relevance": 5,
            "utility": 70, "impact": 80, "depth": 60}
    verdict = evaluate(dims, tier="T1", kind="资讯", channel="大模型动态")
    assert verdict["axis"] == AXIS_AI
    assert verdict["cross_score"] < 25


def test_rule_axis_keywords_split_two_axes():
    """规则回退也要分两轴，否则模型故障期间 axis 会全部塌成「弱」。"""
    from analyzer.scorer import _rule_based

    power = _rule_based("南方电网变电站招标公告")["dims"]
    assert power["power_relevance"] > power["ai_relevance"]

    ai = _rule_based("多模态大模型 OCR 识别新进展")["dims"]
    assert ai["ai_relevance"] > ai["power_relevance"]

    cross = _rule_based("电网巡检大模型缺陷识别")["dims"]
    assert cross["ai_relevance"] >= 55 and cross["power_relevance"] >= 55


def test_cross_pick_does_not_bypass_the_curation_threshold():
    """交叉分只描述内容属性，不能把低质量条目直接标成推荐。"""
    from analyzer.scoring import is_cross_pick

    dims = {"firsthand": 90, "ai_relevance": 45, "power_relevance": 95,
            "utility": 20, "impact": 40, "depth": 15}
    verdict = evaluate(dims, tier="T1", kind="资讯", channel="招标公告")
    assert verdict["axis"] == AXIS_CROSS
    assert verdict["quality"] < 60
    assert verdict["cross_pick"] is True
    assert verdict["curated"] is False

    assert is_cross_pick(90, 90, AXIS_AI) is False
    assert is_cross_pick(90, 90, AXIS_POWER) is False


def test_cross_pick_still_requires_a_quality_floor():
    """交叉但内容极差（营销稿）不该直通。"""
    dims = {"firsthand": 10, "ai_relevance": 60, "power_relevance": 60,
            "utility": 5, "impact": 5, "depth": 5}
    verdict = evaluate(dims, tier="T2", kind="资讯", channel="行业动态")
    assert verdict["axis"] == AXIS_CROSS
    assert verdict["cross_pick"] is False
    assert verdict["curated"] is False
