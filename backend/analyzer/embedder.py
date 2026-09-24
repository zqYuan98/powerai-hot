"""embedding 角色客户端（OpenAI 兼容 /v1/embeddings，默认硅基流动 BGE-M3）。

未配置 EMBEDDING_API_KEY 时返回 None —— 调用方跳过聚类（自成一簇），链路不断。
"""
from __future__ import annotations

import httpx

from core.config import settings


def embed(text: str) -> list[float] | None:
    if not settings.embedding_api_key:
        return None
    from core.runtime import runtime

    runtime.record("embedder", tokens=len(text) // 2)
    resp = httpx.post(
        settings.embedding_api_url,
        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        json={"model": settings.embedding_model, "input": text[:1600]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
