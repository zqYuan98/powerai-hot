import analyzer.embedder as emb_mod
from analyzer.embedder import embed
from core.config import settings


def test_no_key_returns_none():
    assert embed("任意文本") is None  # conftest 已清空 key


def test_calls_api_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "embedding_api_key", "sk-test")

    class FakeResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    captured = {}
    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(emb_mod.httpx, "post", fake_post)
    vec = embed("标题。摘要" * 500)
    assert vec == [0.1, 0.2, 0.3]
    assert captured["json"]["model"] == "BAAI/bge-m3"
    assert len(captured["json"]["input"]) <= 1600  # 超长截断
