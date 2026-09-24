"""RSS full text capture: content first, long HTML summary second."""
import sys
from types import SimpleNamespace

from collector.rss import RssCollector


def _entry(**kw):
    entry = SimpleNamespace(title="title", link="https://x/a", summary="", published_parsed=None)
    for key, value in kw.items():
        setattr(entry, key, value)
    return entry


def _fetch(monkeypatch, entry):
    class FakeFP:
        @staticmethod
        def parse(data):
            return SimpleNamespace(entries=[entry], bozo=False)

    monkeypatch.setitem(sys.modules, "feedparser", FakeFP)
    monkeypatch.setattr("collector.rss.validate_feed_url", lambda url: None)
    monkeypatch.setattr(
        "collector.rss.httpx.get",
        lambda *a, **k: SimpleNamespace(
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=b"<rss/>",
            text="<rss/>",
        ),
    )
    return RssCollector("https://feed.example/rss").fetch()


def test_prefers_content_encoded(monkeypatch):
    entry = _entry(summary="short", content=[SimpleNamespace(value="<p>complete body</p>" * 3)])
    out = _fetch(monkeypatch, entry)
    assert out[0].content_html and "complete body" in out[0].content_html


def test_long_html_description_used_as_fulltext(monkeypatch):
    entry = _entry(summary="<p>" + "long rich description. " * 80 + "</p>")
    out = _fetch(monkeypatch, entry)
    assert out[0].content_html and "long rich description" in out[0].content_html


def test_short_summary_not_treated_as_fulltext(monkeypatch):
    entry = _entry(summary="<p>only one sentence</p>")
    out = _fetch(monkeypatch, entry)
    assert out[0].content_html is None
    assert out[0].content == "only one sentence"
