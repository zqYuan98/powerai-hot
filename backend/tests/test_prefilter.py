from analyzer import prefilter as pf


def test_stub_mode_power_keyword_relevant():
    # 无 API Key（默认）走规则回退；规划关键词命中频道规则
    r = pf.prefilter("国家电网发布特高压建设新规划")
    assert r["relevant"] is True and r["domain"] == "电力"
    assert r["channel"] == "国网规划"


def test_stub_mode_ai_keyword_relevant():
    r = pf.prefilter("Qwen 发布新一代多模态大模型")
    assert r["relevant"] is True and r["domain"] == "AI技术"
    assert r["channel"] == "大模型动态"


def test_stub_mode_irrelevant():
    r = pf.prefilter("某公司发布季度财务报告会议通知")
    assert r == {"relevant": False, "domain": "无关", "channel": None}


def test_stub_mode_no_channel_rule_returns_none():
    r = pf.prefilter("变电站红外测温数据分析")
    assert r["relevant"] is True and r["channel"] is None  # 交给采集器默认频道


def test_hard_noise_blocked_without_model_call(monkeypatch):
    # 电商促销/娱乐类硬噪音：模型调用之前就打回（get_analyzer 不应被触碰）
    def boom(*a, **k):
        raise AssertionError("hard noise 不应调用模型")
    monkeypatch.setattr(pf, "get_analyzer", boom)
    r = pf.prefilter("双11大促开启，券后价直降千元速来下单")
    assert r == {"relevant": False, "domain": "无关", "channel": None}


def test_hard_noise_spared_when_power_or_ai_signal(monkeypatch):
    # 命中噪音词但带电力/AI 信号 → 不硬拦，正常走模型/规则
    class Fake:
        def complete(self, system, prompt, **kw):
            return '{"relevant": true, "domain": "AI技术", "channel": "大模型动态"}'
    monkeypatch.setattr(pf, "get_analyzer", lambda *a, **k: Fake())
    r = pf.prefilter("京东云促销背后：电力大模型如何降低算力成本")
    assert r["relevant"] is True


def test_model_json_parsed(monkeypatch):
    class Fake:
        def complete(self, system, prompt, **kw):
            return '{"relevant": true, "domain": "AI技术", "channel": "前沿论文"}'
    monkeypatch.setattr(pf, "get_analyzer", lambda *a, **k: Fake())
    assert pf.prefilter("anything") == {"relevant": True, "domain": "AI技术", "channel": "前沿论文"}


def test_model_invalid_channel_becomes_none(monkeypatch):
    class Fake:
        def complete(self, system, prompt, **kw):
            return '{"relevant": true, "domain": "电力", "channel": "不存在频道"}'
    monkeypatch.setattr(pf, "get_analyzer", lambda *a, **k: Fake())
    assert pf.prefilter("x")["channel"] is None


def test_model_garbage_falls_back_to_rules(monkeypatch):
    class Fake:
        def complete(self, system, prompt, **kw):
            return "not json at all"
    monkeypatch.setattr(pf, "get_analyzer", lambda *a, **k: Fake())
    r = pf.prefilter("变电站巡检机器人招标公告")
    assert r["relevant"] is True and r["domain"] == "电力" and r["channel"] == "招标公告"
