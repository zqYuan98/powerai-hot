from analyzer import enricher


def test_stub_mode_passthrough():
    r = enricher.enrich("Some English Title", "abstract")
    assert r == {"title_zh": "", "summary": "Some English Title", "tags": [], "org": "行业"}


def test_model_json_parsed(monkeypatch):
    payload = ('{"title_zh": "统一文档理解模型", "summary": "提出X方法做文档理解",'
               ' "tags": ["论文", "OCR"], "org": "arXiv"}')

    class Fake:
        def complete(self, system, prompt, **kw):
            return payload

    monkeypatch.setattr(enricher, "get_analyzer", lambda *a, **k: Fake())
    r = enricher.enrich("DocFormer v3", "abstract...")
    assert r["title_zh"] == "统一文档理解模型"
    assert r["tags"] == ["论文", "OCR"] and r["org"] == "arXiv"


def test_model_string_tags_split(monkeypatch):
    class Fake:
        def complete(self, system, prompt, **kw):
            return '{"title_zh": "", "summary": "s", "tags": "论文，OCR", "org": "行业"}'

    monkeypatch.setattr(enricher, "get_analyzer", lambda *a, **k: Fake())
    assert enricher.enrich("t")["tags"] == ["论文", "OCR"]
