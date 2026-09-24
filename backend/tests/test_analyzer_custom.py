"""CustomAnalyzer：OpenAI 兼容自定义端点——stub / URL 补全 / 鉴权头 / 请求形状。"""
import pytest

import analyzer.custom as custom_mod
from analyzer.custom import CustomAnalyzer, _chat_completions_url
from core.runtime import _Runtime


def test_custom_stub_without_url(monkeypatch):
    monkeypatch.setattr(custom_mod.settings, "custom_api_url", "")
    out = CustomAnalyzer().complete("system", "评估这条新闻")
    assert out.startswith("[custom stub]")


def test_chat_completions_url_normalization():
    assert _chat_completions_url("https://api.example.com/v1") == "https://api.example.com/v1/chat/completions"
    assert _chat_completions_url("https://api.example.com/v1/") == "https://api.example.com/v1/chat/completions"
    assert _chat_completions_url("https://api.example.com/v1/chat/completions") == "https://api.example.com/v1/chat/completions"


class _FakeResponse:
    def __init__(self, content="维度分：85"):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _configure(monkeypatch, *, url="https://api.example.com/v1", key="sk-custom", model="my-model"):
    monkeypatch.setattr(custom_mod.settings, "custom_api_url", url)
    monkeypatch.setattr(custom_mod.settings, "custom_api_key", key)
    monkeypatch.setattr(custom_mod.settings, "custom_model", model)


def test_custom_calls_openai_compatible_endpoint(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(custom_mod.httpx, "post", fake_post)
    out = CustomAnalyzer().complete("你是评分员", "给这篇文章打分", max_tokens=256, temperature=0.1)

    assert out == "维度分：85"
    call = calls[0]
    assert call["url"] == "https://api.example.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-custom"
    assert call["json"]["model"] == "my-model"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "你是评分员"},
        {"role": "user", "content": "给这篇文章打分"},
    ]
    assert call["json"]["max_tokens"] == 256


def test_custom_key_optional_for_private_deployments(monkeypatch):
    _configure(monkeypatch, key="")
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr(custom_mod.httpx, "post", fake_post)
    CustomAnalyzer().complete("s", "p")
    assert "Authorization" not in captured["headers"]


def test_custom_requires_model_name(monkeypatch):
    _configure(monkeypatch, model="")
    with pytest.raises(ValueError):
        CustomAnalyzer().complete("s", "p")


def test_runtime_accepts_custom_rejects_claude():
    r = _Runtime()
    r.set_provider("custom")
    assert r.provider == "custom"
    with pytest.raises(ValueError):
        r.set_provider("claude")
