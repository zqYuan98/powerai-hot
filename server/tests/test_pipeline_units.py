"""管线纯逻辑单测（不需要数据库）。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.collectors.textutil import CN_TZ
from app.llm.client import extract_json
from app.models.enums import Channel
from app.pipeline.grounding import ground_lead
from app.pipeline.llm_schemas import AnalyzeOutput
from app.pipeline.notify import rule_matches, worth_pushing
from app.pipeline.rules import hard_noise, rule_channel
from app.pipeline.scoring import Dims, compute_score, is_selected
from app.pipeline.stories import bigrams, heat_of, jaccard, normalize_key
from app.pipeline.tuning import DimWeights, Tuning

# ---------- 规则 ----------

@pytest.mark.parametrize(
    ("title", "channel"),
    [
        ("某供电局2026年配网工程中标候选人公示", Channel.AWARD),
        ("国网某省电力公司输电线路无人机巡检服务公开招标公告", Channel.TENDER),
        ("某500千伏输变电工程获核准", Channel.PROJECT),
        ("关于印发《电力现货市场基本规则》的通知", Channel.MARKET),
        ("国家能源局印发配电网高质量发展实施方案", Channel.POLICY),
        ("南方电网十五五数字化规划发布", Channel.PLANNING),
        ("某地举办电力行业技能竞赛", None),
    ],
)
def test_rule_channel(title, channel):
    assert rule_channel(title) == channel


def test_hard_noise_blocks_non_power_procurement_even_with_power_words():
    assert hard_noise("某供电公司职工食堂食材采购项目") is not None
    assert hard_noise("双11 手机促销") is not None
    assert hard_noise("京东云发布电力行业大模型") is None  # 有电力信号，交给模型细判
    assert hard_noise("变电站在线监测装置采购") is None


# ---------- 打分：设置页参数必须真实生效 ----------

def test_score_uses_weights_and_tier():
    dims = Dims(relevance=10, opportunity=10, certainty=5, timeliness=5, impact=5)
    t = Tuning()
    base = compute_score(dims, "T2", t)
    assert compute_score(dims, "T1", t) == pytest.approx(min(base * 1.2, 100), abs=0.1)
    heavy = Tuning(weights=DimWeights(relevance=1, opportunity=1, certainty=0, timeliness=0, impact=0))
    assert compute_score(dims, "T2", heavy) == 100.0
    assert compute_score(dims, "T2", t, is_hype=True) == pytest.approx(base * 0.7, abs=0.1)


def test_threshold_changes_selection():
    t = Tuning()
    assert is_selected(62, "T1", t)
    assert not is_selected(62, "T2", t)
    assert not is_selected(62, "T1", Tuning(thresholds={"T1": 80, "T1_5": 80, "T2": 80}))


def test_pure_power_tender_can_reach_selected():
    """旧系统的根本缺陷：纯电力招标因「研究主线关键词」口径几乎进不了精选。"""
    dims = Dims(relevance=9, opportunity=8, certainty=9, timeliness=8, impact=5)
    t = Tuning()
    assert is_selected(compute_score(dims, "T1", t), "T1", t)


# ---------- grounding ----------

TENDER_TEXT = """某省电力公司2026年第三批输电线路无人机巡检服务招标公告
招标编号：GW-2026-0931，招标人：国网某省电力有限公司。
项目概况：覆盖 500kV 及 220kV 线路，预算金额 1,280.5 万元。
投标截止时间：2026年10月15日 09:30。"""


def test_grounding_keeps_supported_fields():
    lead = {
        "project_name": "2026年第三批输电线路无人机巡检服务",
        "owner": "国网某省电力有限公司",
        "bid_no": "GW-2026-0931",
        "amount_wan": 1280.5,
        "voltage_kv": 500,
        "deadline_at": datetime(2026, 10, 15, 9, 30, tzinfo=CN_TZ),
        "winner": None,
    }
    r = ground_lead(lead, TENDER_TEXT)
    assert r.dropped == []
    assert r.values["amount_wan"] == Decimal("1280.5")


def test_grounding_drops_hallucinated_fields():
    lead = {
        "owner": "南方电网广东公司",       # 原文没有
        "bid_no": "GW-2026-9999",          # 编号不对
        "amount_wan": 3000,                # 金额不对
        "voltage_kv": 110,                 # 原文没有 110kV
        "deadline_at": datetime(2026, 10, 20, tzinfo=CN_TZ),
        "project_name": "",
    }
    r = ground_lead(lead, TENDER_TEXT)
    assert set(r.dropped) == {"owner", "bid_no", "amount_wan", "voltage_kv", "deadline_at"}
    assert r.values["project_name"] is None


def test_grounding_tolerates_org_full_name_expansion():
    title = "国网江苏电力2026年物资第五次公开谈判采购项目推荐的成交候选人公示"
    assert ground_lead({"owner": "国网江苏省电力有限公司"}, title).dropped == []
    assert ground_lead({"owner": "国网山东省电力公司"}, title).dropped == ["owner"]  # 换了省份仍要丢
    assert ground_lead({"owner": "有限公司"}, title).dropped == ["owner"]           # 主干过短不放行


def test_grounding_accepts_amount_in_yuan_or_yi():
    assert ground_lead({"amount_wan": 1280.5}, "预算 12805000 元").dropped == []
    assert ground_lead({"amount_wan": 25000}, "总投资 2.5 亿元").dropped == []


# ---------- LLM 输出解析 ----------

def test_extract_json_tolerates_think_and_fences():
    raw = '<think>先想想</think>\n```json\n{"a": 1}\n```'
    assert extract_json(raw) == {"a": 1}
    assert extract_json('结果如下：{"b": [1, 2]} 以上') == {"b": [1, 2]}
    with pytest.raises(ValueError):
        extract_json("没有 JSON")


def test_analyze_output_is_lenient():
    out = AnalyzeOutput.model_validate({
        "channel": "招标",  # 非法代码 → industry（随后由规则纠正）
        "scores": {"relevance": 15, "opportunity": "8", "certainty": None},
        "tags": "变电站,无人机,巡检,国网,多余",
        "event_key": "GD 500kV Substation!",
        "lead": {"deadline": "2026-10-15 09:30", "amount_wan": "1,280.5", "stage": "bogus", "match_score": 300},
    })
    assert out.channel == "industry"
    assert out.scores.relevance == 10 and out.scores.opportunity == 8 and out.scores.certainty == 0
    assert len(out.tags) == 4
    assert out.event_key == "gd-500kv-substation"
    assert out.lead is not None and out.lead.stage == "unknown" and out.lead.match_score == 100
    assert out.lead.deadline == datetime(2026, 10, 15, 9, 30, tzinfo=CN_TZ)


# ---------- 归并与热度 ----------

def test_bigram_jaccard_matches_reworded_titles():
    a = bigrams("某省220kV变电站新建工程施工招标公告")
    b = bigrams("某省220kV变电站新建工程施工招标")
    c = bigrams("国家能源局发布电力现货市场规则")
    assert jaccard(a, b) >= 0.9
    assert jaccard(a, c) < 0.2


def test_normalize_key_ignores_punctuation():
    assert normalize_key("GW-2026 / 0931") == normalize_key("gw20260931")


def test_heat_counts_independent_sources_with_half_life():
    now = datetime(2026, 9, 28, tzinfo=UTC)
    assert heat_of([now, now, now], now) == 30.0
    assert heat_of([now - timedelta(hours=24)], now) == 5.0


# ---------- 订阅匹配 ----------

def _item(**kw):
    lead = kw.pop("lead", None)
    base = dict(title="某市输电线路无人机巡检服务招标", title_zh=None, summary="", tags=[], province="广东",
                channel="tender", selected=False, lead=lead)
    base.update(kw)
    return SimpleNamespace(**base)


def _rule(**kw):
    base = dict(keywords=[], provinces=[], channels=[], min_amount_wan=None, min_voltage_kv=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_rule_matching_filters():
    lead = SimpleNamespace(amount_wan=Decimal(500), voltage_kv=220, match_score=70)
    item = _item(lead=lead)
    assert rule_matches(_rule(keywords=["无人机巡检"]), item)
    assert not rule_matches(_rule(keywords=["特高压"]), item)
    assert not rule_matches(_rule(provinces=["云南"]), item)
    assert rule_matches(_rule(min_amount_wan=Decimal(300), min_voltage_kv=110), item)
    assert not rule_matches(_rule(min_amount_wan=Decimal(800)), item)
    assert not rule_matches(_rule(min_voltage_kv=110), _item(lead=None))


def test_worth_pushing_high_match_lead_even_if_not_selected():
    t = Tuning()
    assert worth_pushing(_item(lead=SimpleNamespace(match_score=75)), t)
    assert not worth_pushing(_item(lead=SimpleNamespace(match_score=30)), t)
    assert worth_pushing(_item(selected=True), t)
