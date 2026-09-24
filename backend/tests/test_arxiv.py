from pathlib import Path

import collector.arxiv as arxiv_mod
from collector.arxiv import ArxivCollector

FIXTURE = (Path(__file__).parent / "fixtures" / "arxiv.atom").read_text(encoding="utf-8")


class FakeResp:
    status_code = 200
    text = FIXTURE

    def raise_for_status(self):
        pass


def test_fetch_parses_entries(monkeypatch):
    monkeypatch.setattr(arxiv_mod.httpx, "get", lambda *a, **k: FakeResp())
    items = ArxivCollector(limit=10).fetch().items
    assert len(items) == 2
    first = items[0]
    assert first.kind == "论文"
    assert first.channel == "前沿论文"
    assert "DocMamba" in first.title and "\n" not in first.title  # 标题换行被清理
    assert first.meta["arxiv_id"] == "2507.01234v1"
    assert first.meta["pdf_url"] == "http://arxiv.org/pdf/2507.01234v1"
    assert first.meta["authors"] == ["Alice Zhang", "Bob Li"]
    assert first.content.startswith("We propose DocMamba")
    assert first.published_label == "2026-07-02"
    assert first.url == "http://arxiv.org/abs/2507.01234v1"


def test_collector_metadata():
    c = ArxivCollector()
    assert c.tier == "T1" and c.group == "papers" and c.source_name == "arXiv"


def test_fetch_network_error_returns_collector_result(monkeypatch):
    """网络故障要变成 CollectorResult，而不是向上抛异常。

    契约统一后 ingest 依据 transport_status 记录信源健康；
    裸抛异常会被记成「采集器崩溃」，丢掉可诊断的分类。
    """
    def boom(*a, **k):
        raise arxiv_mod.httpx.ConnectError("net down")
    monkeypatch.setattr(arxiv_mod.httpx, "get", boom)

    result = ArxivCollector().fetch()
    assert result.transport_status == "network_error"
    assert result.items == []
