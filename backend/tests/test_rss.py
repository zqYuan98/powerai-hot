import sys
import types

import httpx

from collector.rss import RssCollector, _strip_html


def test_strip_html():
    assert _strip_html("<p>nanoGPT: <b>minimal</b> GPT trainer&nbsp;</p>") == "nanoGPT: minimal GPT trainer"
    assert len(_strip_html("x" * 5000)) == 1000


def test_fetch_passes_entry_summary_as_content(monkeypatch):
    entry = types.SimpleNamespace(
        title="karpathy/nanoGPT",
        link="https://github.com/karpathy/nanoGPT",
        summary="<p>The simplest, fastest repository for training/finetuning medium-sized GPTs.</p>",
        published_parsed=None,
    )
    fake = types.SimpleNamespace(parse=lambda data: types.SimpleNamespace(entries=[entry], bozo=False))
    monkeypatch.setitem(sys.modules, "feedparser", fake)
    monkeypatch.setattr("collector.rss.validate_feed_url", lambda url: None)
    monkeypatch.setattr(
        "collector.rss.httpx.get",
        lambda *a, **k: types.SimpleNamespace(
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=b"<rss/>",
            text="<rss/>",
        ),
    )

    result = RssCollector("https://x.test/feed", source_name="test source").fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    assert len(result) == 1
    assert result[0].content.startswith("The simplest, fastest repository")
    assert "<p>" not in result[0].content


def test_fetch_reports_unsafe_scheme_as_schema_error():
    result = RssCollector("file:///etc/passwd").fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"
    assert "unsafe" in result.error_summary


def test_fetch_rejects_initial_loopback_without_request(monkeypatch):
    calls = []
    monkeypatch.setattr("collector.rss.httpx.get", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("request should not be sent")))

    result = RssCollector("http://127.0.0.1:8000/feed.xml").fetch()

    assert calls == []
    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"
    assert result.error_summary


def test_fetch_revalidates_redirect_target_and_blocks_metadata_ip(monkeypatch):
    fake = types.SimpleNamespace(parse=lambda data: types.SimpleNamespace(entries=[], bozo=False))
    monkeypatch.setitem(sys.modules, "feedparser", fake)
    validated = []

    def fake_validate(url):
        validated.append(url)
        if "169.254.169.254" in url:
            raise ValueError("blocked private address with token=secret")

    monkeypatch.setattr("collector.rss.validate_feed_url", fake_validate, raising=False)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return types.SimpleNamespace(
            status_code=302,
            headers={"location": "http://169.254.169.254/latest/meta-data"},
            content=b"",
            text="",
        )

    monkeypatch.setattr("collector.rss.httpx.get", fake_get)

    result = RssCollector("https://public.example/feed").fetch()

    assert validated == ["https://public.example/feed", "http://169.254.169.254/latest/meta-data"]
    assert calls == ["https://public.example/feed"]
    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"
    assert "secret" not in (result.error_summary or "")


def test_fetch_follows_safe_relative_redirect(monkeypatch):
    entry = types.SimpleNamespace(
        title="redirected feed",
        link="https://public.example/item",
        summary="ok",
        published_parsed=None,
    )
    fake = types.SimpleNamespace(parse=lambda data: types.SimpleNamespace(entries=[entry], bozo=False))
    monkeypatch.setitem(sys.modules, "feedparser", fake)
    validated = []
    monkeypatch.setattr("collector.rss.validate_feed_url", lambda url: validated.append(url), raising=False)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url == "https://public.example/feed":
            return types.SimpleNamespace(
                status_code=302,
                headers={"location": "/actual.xml"},
                content=b"",
                text="",
            )
        return types.SimpleNamespace(
            status_code=200,
            headers={"content-type": "application/atom+xml"},
            content=b"<feed/>",
            text="<feed/>",
        )

    monkeypatch.setattr("collector.rss.httpx.get", fake_get)

    result = RssCollector("https://public.example/feed").fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    assert validated == ["https://public.example/feed", "https://public.example/actual.xml"]
    assert [url for url, _ in calls] == ["https://public.example/feed", "https://public.example/actual.xml"]
    assert all(call[1]["follow_redirects"] is False for call in calls)


def test_fetch_reports_redirect_loop_limit(monkeypatch):
    fake = types.SimpleNamespace(parse=lambda data: types.SimpleNamespace(entries=[], bozo=False))
    monkeypatch.setitem(sys.modules, "feedparser", fake)
    monkeypatch.setattr("collector.rss.validate_feed_url", lambda url: None, raising=False)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return types.SimpleNamespace(
            status_code=302,
            headers={"location": "/feed"},
            content=b"",
            text="",
        )

    monkeypatch.setattr("collector.rss.httpx.get", fake_get)

    result = RssCollector("https://public.example/feed").fetch()

    assert len(calls) == 6
    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"
    assert "redirect" in (result.error_summary or "").lower()


def test_fetch_reports_feedparser_bozo(monkeypatch):
    fake = types.SimpleNamespace(
        parse=lambda data: types.SimpleNamespace(entries=[], bozo=True, bozo_exception=ValueError("bad xml"))
    )
    monkeypatch.setitem(sys.modules, "feedparser", fake)
    monkeypatch.setattr("collector.rss.validate_feed_url", lambda url: None)
    monkeypatch.setattr(
        "collector.rss.httpx.get",
        lambda *a, **k: types.SimpleNamespace(
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=b"<rss>",
            text="<rss>",
        ),
    )

    result = RssCollector("https://x.test/feed").fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "parse_error"
    assert "bad xml" in result.error_summary
