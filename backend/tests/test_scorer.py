from analyzer import scorer
from analyzer.scoring import DIM_KEYS


def test_stub_mode_returns_all_dims_and_reason():
    r = scorer.score("国家电网变电站无人机巡检 AI 识别项目招标")
    # 单一职责：只评审，不做内容生成。fallback 是降级标记，不是生成内容。
    assert set(r.keys()) == {"dims", "reason", "fallback"}
    assert r["fallback"] is True  # stub 模式即降级
    assert set(r["dims"].keys()) == set(DIM_KEYS)
    assert all(0 <= v <= 100 for v in r["dims"].values())
    assert r["reason"]


def test_model_json_parsed(monkeypatch):
    payload = ('{"reason": "与OCR方向直接相关",'
               ' "dims": {"firsthand": 95, "ai_relevance": 88, "power_relevance": 60, "utility": 70, "impact": 60, "depth": 80}}')

    class Fake:
        def complete(self, system, prompt, **kw):
            assert kw.get("temperature") == 0.1  # 打分低温采样
            return payload

    monkeypatch.setattr(scorer, "get_analyzer", lambda *a, **k: Fake())
    r = scorer.score("DocFormer v3", content="abstract...")
    assert r["dims"]["ai_relevance"] == 88 and r["reason"] == "与OCR方向直接相关"


def test_model_dims_clamped(monkeypatch):
    payload = ('{"reason": "r", "dims": {"firsthand": 999, "ai_relevance": -5,'
               ' "utility": 50, "impact": 50, "depth": 50}}')

    class Fake:
        def complete(self, system, prompt, **kw):
            return payload

    monkeypatch.setattr(scorer, "get_analyzer", lambda *a, **k: Fake())
    r = scorer.score("t")
    assert r["dims"]["firsthand"] == 100 and r["dims"]["ai_relevance"] == 0


def test_model_garbage_falls_back(monkeypatch):
    class Fake:
        def complete(self, system, prompt, **kw):
            return "not json"

    monkeypatch.setattr(scorer, "get_analyzer", lambda *a, **k: Fake())
    r = scorer.score("布控球边缘AI方案")
    assert r["dims"]["ai_relevance"] > 20  # 规则回退按关键词估分


def test_model_result_is_not_marked_fallback(monkeypatch):
    """模型正常出分时 fallback 必须为 False —— 回填/监控据此区分真分与估分。"""
    payload = ('{"reason": "r", "dims": {"firsthand": 90, "ai_relevance": 80,'
               ' "power_relevance": 70, "utility": 60, "impact": 50, "depth": 40}}')

    class Fake:
        def complete(self, system, prompt, **kw):
            return payload

    monkeypatch.setattr(scorer, "get_analyzer", lambda *a, **k: Fake())
    assert scorer.score("x")["fallback"] is False


def test_empty_model_content_falls_back_and_is_marked(monkeypatch):
    """推理模型可能返回空 content（预算被思维链吃光）——必须标记为降级。"""

    class Empty:
        def complete(self, system, prompt, **kw):
            return ""

    monkeypatch.setattr(scorer, "get_analyzer", lambda *a, **k: Empty())
    result = scorer.score("南方电网变电站招标")
    assert result["fallback"] is True
