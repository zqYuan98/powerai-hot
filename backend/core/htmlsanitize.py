"""HTML 白名单消毒（标准库实现，零新依赖）。

RSS/公众号桥的富文本是不可信输入：只保留阅读必需的结构标签，
属性只留 a[href] / img[src]（http/https）+ alt/title，其余全部丢弃；
script/style/iframe 等危险标签连同内容整段删除。
"""
from __future__ import annotations

import html
from html.parser import HTMLParser

_ALLOWED = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "em", "strong", "b", "i", "u", "s", "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "figure", "figcaption", "span", "div",
}
_VOID = {"br", "hr", "img"}
# 这些标签连同其内部内容一起丢弃
_DROP_WITH_CONTENT = {
    "script", "style", "iframe", "form", "object", "embed",
    "svg", "math", "noscript", "head", "title",
}
_URL_ATTRS = {"a": "href", "img": "src"}
_KEEP_ATTRS = {"alt", "title"}


def _safe_url(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith("http://") or v.startswith("https://")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._drop_depth = 0  # >0 表示处于被整段丢弃的标签内部

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_WITH_CONTENT:
            if tag not in _VOID:
                self._drop_depth += 1
            return
        if self._drop_depth or tag not in _ALLOWED:
            return
        keep: list[str] = []
        url_attr = _URL_ATTRS.get(tag)
        for name, value in attrs:
            if value is None:
                continue
            if name == url_attr and _safe_url(value):
                keep.append(f'{name}="{html.escape(value, quote=True)}"')
            elif name in _KEEP_ATTRS:
                keep.append(f'{name}="{html.escape(value, quote=True)}"')
        attr_str = (" " + " ".join(keep)) if keep else ""
        self.out.append(f"<{tag}{attr_str}/>" if tag in _VOID else f"<{tag}{attr_str}>")

    def handle_startendtag(self, tag, attrs):
        # 自闭合语法 <img .../>：按普通起始标签处理（void 标签不再补 end）
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _DROP_WITH_CONTENT:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth or tag not in _ALLOWED or tag in _VOID:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._drop_depth:
            return
        if data:
            self.out.append(html.escape(data))


def sanitize_html(raw: str, max_len: int = 200_000) -> str:
    if not raw or not raw.strip():
        return ""
    parser = _Sanitizer()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return ""  # 解析崩溃宁可不要正文，回退摘要链路
    out = "".join(parser.out).strip()
    if len(out) > max_len:
        out = out[:max_len] + "…]"
    return out
