"""DeepSeek 实现（默认分析模型，OpenAI 兼容接口）。

未配置 DEEPSEEK_API_KEY 时返回离线 stub，保证管线可跑通；
配置后自动走真实接口。
"""
import httpx

from analyzer.base import Analyzer
from core.config import settings

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"


class DeepSeekAnalyzer(Analyzer):
    name = "deepseek"

    def __init__(self, model: str | None = None) -> None:
        self.api_key = settings.deepseek_api_key
        self.model = model or MODEL

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512,
                 temperature: float = 0.3) -> str:
        from core.runtime import runtime

        runtime.record(self.name, tokens=len(prompt) // 4)
        if not self.api_key:
            # 离线 stub —— 无 Key 也能跑通整条链路（配合规则打分回退）。
            return f"[deepseek stub] {prompt[:80]}"

        resp = httpx.post(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
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
