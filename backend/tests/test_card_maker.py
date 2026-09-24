from analyzer import card_maker as cm

CATEGORIES = ["视觉/OCR", "大模型", "电力AI应用", "其他"]


def test_stub_mode_rule_fallback():
    r = cm.make_card("DocFormer: OCR-free document understanding", "文档理解新方法")
    assert r["category"] == "视觉/OCR"
    assert all(k in r for k in ("problem", "method", "conclusion", "power_relevance"))


def test_stub_mode_power_category():
    r = cm.make_card("变电站无人机巡检缺陷识别方案落地", "")
    assert r["category"] == "电力AI应用"


def test_model_json_parsed(monkeypatch):
    payload = ('{"category": "大模型", "problem": "p", "method": "m",'
               ' "conclusion": "c", "power_relevance": "r"}')

    class Fake:
        def complete(self, system, prompt, *, max_tokens=512):
            return payload

    monkeypatch.setattr(cm, "get_analyzer", lambda *a, **k: Fake())
    r = cm.make_card("GPT-5.5 发布", "支持多模态")
    assert r == {"category": "大模型", "problem": "p", "method": "m",
                 "conclusion": "c", "power_relevance": "r"}


def test_model_invalid_category_falls_back(monkeypatch):
    payload = '{"category": "不存在", "problem": "p", "method": "m", "conclusion": "c", "power_relevance": "r"}'

    class Fake:
        def complete(self, system, prompt, *, max_tokens=512):
            return payload

    monkeypatch.setattr(cm, "get_analyzer", lambda *a, **k: Fake())
    assert cm.make_card("x", "")["category"] == "其他"
