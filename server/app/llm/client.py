"""LLM 客户端：OpenAI 兼容端点 + JSON 模式 + Pydantic 校验 + 真实用量记账。

失败分两类：
- 可重试（超时/429/5xx）：内部指数退避重试，仍失败则抛 LlmError(retryable=True)，条目留待下轮重试。
- 不可自愈（401/402/400 模型名下线等）：立即抛 LlmError(retryable=False)。
  2026-07 deepseek-chat 下线曾让旧系统静默退化为关键词打分 19 小时——新系统绝不静默降级。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

import httpx
import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from app.config import settings

log = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / "prompts"
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LlmError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class CallRecord:
    task: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_yuan: float
    latency_ms: int
    ok: bool
    error: str | None = None


Recorder = Callable[[CallRecord], Awaitable[None]]
# 记账时给任务名加前缀（如评测记为 eval:analyze），让用量页把这部分花费单独列出来
call_tag: ContextVar[str | None] = ContextVar("call_tag", default=None)
Reasoning = Literal["off", "low", "high"]


async def _db_recorder(rec: CallRecord) -> None:
    from app.db import SessionLocal
    from app.models import LlmCall

    try:
        async with SessionLocal() as session:
            session.add(LlmCall(**rec.__dict__))
            await session.commit()
    except Exception:  # 记账失败不影响主流程
        log.exception("记录 LLM 用量失败")


recorder: Recorder = _db_recorder
_semaphore = asyncio.Semaphore(settings.llm_concurrency)


@cache
def _client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "missing",
        timeout=settings.llm_timeout_s,
        max_retries=0,  # 重试由这里统一控制，便于区分错误类型
    )


@cache
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def extract_json(text: str) -> Any:
    """容忍推理模型残留的 <think> 块、markdown 代码围栏与前后缀文字。"""
    text = _THINK_RE.sub("", text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("输出中没有 JSON")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def _cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = settings.llm_prices.get(model, (0.0, 0.0))
    return round((prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000, 6)


def _classify(exc: Exception) -> LlmError:
    if isinstance(exc, openai.APITimeoutError | openai.APIConnectionError | openai.RateLimitError
                  | openai.InternalServerError):
        return LlmError(f"{type(exc).__name__}: {exc}"[:300], retryable=True)
    if isinstance(exc, openai.APIStatusError):
        body = str(exc.body)[:200] if exc.body else ""
        return LlmError(f"HTTP {exc.status_code} 配置/额度故障（不会自愈）：{body}", retryable=False)
    return LlmError(f"{type(exc).__name__}: {exc}"[:300], retryable=False)


async def complete_json[T: BaseModel](
    *,
    task: str,
    model: str,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int = 1200,
    temperature: float = 0.2,
    attempts: int = 3,
    reasoning: Reasoning = "off",
) -> T:
    if not settings.llm_enabled:
        raise LlmError("未配置 LLM_API_KEY", retryable=False)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # 推理模型默认开启思维链：批量结构化任务关掉（快 30 倍、不会因思维链耗尽预算而返回空内容），
    # 写作类任务用低强度推理。思维链与正式输出共用 max_tokens，开启时追加预算。
    extra: dict[str, Any] = {}
    if settings.llm_thinking_control:
        if reasoning == "off":
            extra["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            extra["reasoning_effort"] = reasoning
            max_tokens += 4000
    if tag := call_tag.get():
        task = f"{tag}:{task}"
    last: LlmError | None = None
    for attempt in range(attempts):
        started = time.monotonic()
        usage = (0, 0)
        try:
            async with _semaphore:
                resp = await _client().chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    **extra,
                )
            if resp.usage:
                usage = (resp.usage.prompt_tokens, resp.usage.completion_tokens)
            content = resp.choices[0].message.content or ""
            if not content.strip():
                # 推理模型预算不足时会出现 content 为空、内容全在 reasoning_content
                raise LlmError("模型返回空内容（max_tokens 可能不足）", retryable=True)
            try:
                result = schema.model_validate(extract_json(content))
            except (ValueError, ValidationError) as exc:
                raise LlmError(f"输出不符合格式：{exc}"[:300], retryable=True) from exc
        except LlmError as exc:
            last = exc
        except Exception as exc:  # openai 异常统一分类
            last = _classify(exc)
        else:
            await recorder(CallRecord(task, model, *usage, _cost(model, *usage),
                                      int((time.monotonic() - started) * 1000), ok=True))
            return result
        await recorder(CallRecord(task, model, *usage, _cost(model, *usage),
                                  int((time.monotonic() - started) * 1000), ok=False, error=str(last)))
        if not last.retryable:
            raise last
        if attempt + 1 < attempts:
            await asyncio.sleep(min(2 ** attempt * 2, 20))
    assert last is not None
    raise last


@cache
def _embed_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key or "missing",
        timeout=30,
        max_retries=2,
    )


async def rerank(query: str, documents: Sequence[str]) -> list[float] | None:
    """返回与 documents 一一对应的相关度（0–1）；未配置时返回 None。"""
    if not (settings.embedding_enabled and settings.rerank_model) or not documents:
        return None
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{settings.embedding_base_url.rstrip('/')}/rerank",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.rerank_model, "query": query,
                      "documents": [d[:1000] for d in documents], "top_n": len(documents)},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        await recorder(CallRecord("rerank", settings.rerank_model, 0, 0, 0.0,
                                  int((time.monotonic() - started) * 1000), ok=False, error=str(exc)[:300]))
        raise LlmError(f"rerank 失败：{exc}"[:300], retryable=True) from exc
    scores = [0.0] * len(documents)
    for row in data.get("results") or []:
        scores[row["index"]] = float(row["relevance_score"])
    tokens = int((data.get("meta") or {}).get("tokens", {}).get("input_tokens", 0) or 0)
    await recorder(CallRecord("rerank", settings.rerank_model, tokens, 0, 0.0,
                              int((time.monotonic() - started) * 1000), ok=True))
    return scores


async def embed(texts: Sequence[str]) -> list[list[float]] | None:
    """未配置 Embedding Key 时返回 None，调用方跳过向量相关步骤。"""
    if not settings.embedding_enabled or not texts:
        return None
    started = time.monotonic()
    try:
        resp = await _embed_client().embeddings.create(
            model=settings.embedding_model, input=[t[:2000] for t in texts]
        )
    except Exception as exc:
        err = _classify(exc)
        await recorder(CallRecord("embed", settings.embedding_model, 0, 0, 0.0,
                                  int((time.monotonic() - started) * 1000), ok=False, error=str(err)))
        raise err from exc
    tokens = resp.usage.prompt_tokens if resp.usage else 0
    await recorder(CallRecord("embed", settings.embedding_model, tokens, 0, 0.0,
                              int((time.monotonic() - started) * 1000), ok=True))
    return [d.embedding for d in resp.data]
