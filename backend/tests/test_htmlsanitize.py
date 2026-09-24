"""白名单消毒器：RSS 富文本是不可信输入，入库前必须清洗。"""
from core.htmlsanitize import sanitize_html


def test_keeps_whitelisted_structure():
    raw = '<p>正文 <strong>加粗</strong></p><ul><li>一</li></ul><pre><code>x=1</code></pre>'
    out = sanitize_html(raw)
    assert "<p>" in out and "<strong>加粗</strong>" in out
    assert "<li>一</li>" in out and "<code>x=1</code>" in out


def test_strips_script_and_event_handlers():
    raw = '<p onclick="evil()">a</p><script>alert(1)</script><img src="https://x/1.png" onerror="evil()">'
    out = sanitize_html(raw)
    assert "script" not in out and "alert" not in out
    assert "onclick" not in out and "onerror" not in out
    assert '<img src="https://x/1.png"' in out


def test_drops_javascript_and_data_urls():
    raw = '<a href="javascript:evil()">x</a><img src="data:text/html;base64,xx">'
    out = sanitize_html(raw)
    assert "javascript:" not in out and "data:" not in out
    assert "<a>x</a>" in out  # 标签保留，危险属性剥掉


def test_drops_style_iframe_form_entirely():
    raw = '<style>p{}</style><iframe src="https://x"></iframe><form><input></form><p>ok</p>'
    out = sanitize_html(raw)
    assert "iframe" not in out and "style" not in out and "input" not in out
    assert "<p>ok</p>" in out


def test_escapes_text_and_truncates():
    assert "&lt;b&gt;" in sanitize_html("<p>a &lt;b&gt; c</p>")
    long = "<p>" + "字" * 300 + "</p>"
    out = sanitize_html(long, max_len=100)
    assert len(out) <= 120 and out.endswith("…]")


def test_empty_and_plain_text():
    assert sanitize_html("") == ""
    assert sanitize_html("纯文本无标签") == "纯文本无标签"
