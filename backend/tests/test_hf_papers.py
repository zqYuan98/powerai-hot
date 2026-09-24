import json
from pathlib import Path

import collector.hf_papers as hf_mod
from collector.hf_papers import HFPapersCollector

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "hf_daily.json").read_text(encoding="utf-8"))


class FakeResp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return FIXTURE


def test_fetch_parses_papers(monkeypatch):
    monkeypatch.setattr(hf_mod.httpx, "get", lambda *a, **k: FakeResp())
    items = HFPapersCollector(limit=10).fetch().items
    assert len(items) == 2
    p = items[0]
    assert p.kind == "论文" and p.channel == "前沿论文"
    assert p.title == "UniOCR: One Model for All Text Recognition Tasks"
    assert p.url == "https://huggingface.co/papers/2507.02001"
    assert p.meta["arxiv_id"] == "2507.02001"
    assert p.meta["pdf_url"] == "https://arxiv.org/pdf/2507.02001"
    assert p.meta["authors"] == ["D. Chen", "E. Liu"]
    assert p.published_label == "2026-07-02"


def test_collector_metadata():
    c = HFPapersCollector()
    assert c.tier == "T1" and c.group == "papers" and c.source_name == "Hugging Face Papers"


def test_limit_respected(monkeypatch):
    monkeypatch.setattr(hf_mod.httpx, "get", lambda *a, **k: FakeResp())
    assert len(HFPapersCollector(limit=1).fetch().items) == 1
