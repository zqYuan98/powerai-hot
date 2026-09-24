"""自定义模型实现（OpenAI 兼容接口，可在管理后台切换）。

适配任何暴露 /chat/completions 的服务：第三方云平台、私有化 vLLM、
Ollama 的 OpenAI 兼容端点等。未配置 CUSTOM_API_URL 时返回离线 stub。
"""
import httpx

from analyzer.base import Analyzer
from core.config import settings


def _chat_completions_url(url: str) -> str:
    """URL 可填基地址（…/v1）或完整地址（…/chat/completions），自动补全。"""
    url = url.rstrip("/")
    return url if url.endswith("/chat/completions") else f"{url}/chat/completions"


class CustomAnalyzer(Analyzer):
    name = "custom"

    def __init__(self) -> None:
        self.api_url = settings.custom_api_url
        self.api_key = settings.custom_api_key
        self.model = settings.custom_model

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512,
                 temperature: float = 0.3) -> str:
        from core.runtime import runtime

        runtime.record(self.name, tokens=len(prompt) // 4)
        if not self.api_url:
            # 离线 stub —— 未配置端点也能跑通整条链路（配合规则打分回退）。
            return f"[custom stub] {prompt[:80]}"
        if not self.model:
            raise ValueError("CUSTOM_MODEL 未配置：自定义模型需同时提供 API 地址与模型名")

        headers = {"Content-Type": "application/json"}
        if self.api_key:  # 私有化部署可能无鉴权，Key 允许留空
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = httpx.post(
            _chat_completions_url(self.api_url),
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
