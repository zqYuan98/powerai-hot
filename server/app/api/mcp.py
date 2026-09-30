"""MCP Server：Streamable HTTP 的无状态子集（每个 POST 一个 JSON-RPC 请求，直接回 JSON，不开 SSE）。

匿名只读，工具与 REST API v1 共用查询和数据契约。协议见 https://modelcontextprotocol.io/specification
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import v1
from app.config import settings
from app.db import get_session
from app.models.enums import (
    CHANNEL_LABELS,
    DOMAIN_LABELS,
    KTYPE_LABELS,
    Channel,
    DigestKind,
    KnowledgeDomain,
    KnowledgeType,
    Stage,
)
from app.schemas.public import V1Item, V1Knowledge

router = APIRouter(tags=["mcp"])
Session = Annotated[AsyncSession, Depends(get_session)]

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "powerai", "title": "电力基建情报站", "version": "1.0.0"}
INSTRUCTIONS = (
    "电力基建（输变电工程、智能运检）中文情报：招标、中标、项目、规划、政策与行业动态。"
    "先用 latest / leads 看最近的内容，用 search 查具体项目或业主，用 hot 与 story 看热点事件；"
    "要专业知识（工艺、规范、方案思路）用 knowledge。"
    "标题与摘要由模型根据原文生成，金额、截止时间等关键信息请以返回的原文链接为准。"
)
STAGE_TEXT = {"planning": "规划", "approval": "核准", "feasibility": "可研", "tendering": "招标中",
              "awarded": "已中标", "construction": "在建", "operation": "投运", "unknown": ""}

ChannelName = Literal["tender", "award", "project", "planning", "policy", "market", "company", "tech", "industry"]
StageName = Literal["planning", "approval", "feasibility", "tendering", "awarded", "construction", "operation"]


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LatestArgs(Args):
    mode: Literal["selected", "all"] = Field("selected", description="selected=精选；all=全部完成精读的动态")
    window: Literal["24h", "7d"] = Field("24h", description="时间范围：过去 24 小时或 7 天")
    channel: ChannelName | None = Field(None, description=(
        "频道：tender 招标、award 中标、project 项目、planning 规划、"
        "policy 政策、market 市场、company 企业、tech 技术、industry 行业"))
    limit: int = Field(10, ge=1, le=30)


class SearchArgs(Args):
    q: str = Field(min_length=1, max_length=100, description="项目名、业主、地区或话题关键词")
    limit: int = Field(10, ge=1, le=20)


class LeadsArgs(Args):
    stage: StageName | None = Field(None, description="项目阶段；tendering=招标中，awarded=已中标")
    province: str | None = Field(None, max_length=16, description="省份，如「江苏」")
    open_only: bool = Field(True, description="只看未截止的（无截止时间的也保留）")
    min_amount_wan: float | None = Field(None, ge=0, description="金额下限（万元）")
    min_voltage_kv: int | None = Field(None, ge=0, description="电压等级下限（kV）")
    q: str | None = Field(None, max_length=100, description="项目名 / 业主 / 标题关键词")
    sort: Literal["recent", "deadline", "amount"] = Field("recent", description="最新发现 / 截止最近 / 金额最大")
    limit: int = Field(10, ge=1, le=30)


class HotArgs(Args):
    limit: int = Field(10, ge=1, le=10)


class StoryArgs(Args):
    story_id: int = Field(ge=1, description="事件 ID，只能来自 hot 或其他工具返回的 story_id，不要猜")


DomainName = Literal["transmission", "substation", "distribution", "civil", "commissioning", "inspection",
                     "renewable", "general"]
KtypeName = Literal["principle", "construction", "standard", "design", "safety", "cost", "bidding", "management",
                    "tech"]


class KnowledgeArgs(Args):
    q: str | None = Field(None, max_length=100, description="关键词，如「GIS 安装」「接地电阻」「跨越施工」")
    domain: DomainName | None = Field(None, description=(
        "专业：transmission 输电线路、substation 变电站、distribution 配电网、civil 土建与基础、"
        "commissioning 调试试验、inspection 智能运检、renewable 新能源与储能、general 综合"))
    ktype: KtypeName | None = Field(None, description=(
        "类型：principle 原理、construction 施工工艺、standard 标准规范、design 设计方案、safety 安全与事故、"
        "cost 造价定额、bidding 招投标实务、management 项目管理、tech 新技术装备"))
    limit: int = Field(10, ge=1, le=20)


class DailyArgs(Args):
    date: dt.date | None = Field(None, description="YYYY-MM-DD；不填取最新一期")
    kind: Literal["daily", "weekly"] = "daily"


def _time(item: V1Item) -> str:
    return item.first_seen_at.astimezone(settings.tz).strftime("%m-%d %H:%M")


def _render_item(i: int, item: V1Item) -> str:
    lines = [f"{i}. [{CHANNEL_LABELS.get(item.channel, item.channel)}] {item.title}（{item.source} · {_time(item)}）"]
    if lead := item.lead:
        facts = [STAGE_TEXT.get(lead.stage, ""),
                 f"{lead.amount_wan:g} 万元" if lead.amount_wan is not None else "",
                 f"{lead.voltage_kv} kV" if lead.voltage_kv else "",
                 f"业主 {lead.owner}" if lead.owner else "",
                 f"截止 {lead.deadline_at.astimezone(settings.tz):%Y-%m-%d %H:%M}" if lead.deadline_at else ""]
        if facts := [f for f in facts if f]:
            lines.append("   商机：" + " · ".join(facts))
    if item.summary:
        lines.append(f"   {item.summary}")
    lines.append(f"   站内：{item.url} ｜ 原文：{item.source_url}")
    return "\n".join(lines)


def _render_items(title: str, items: list[V1Item]) -> str:
    if not items:
        return f"{title}：没有结果。"
    return f"{title}（{len(items)} 条）\n\n" + "\n\n".join(_render_item(n, it) for n, it in enumerate(items, 1))


ToolResult = tuple[str, dict[str, Any]]


async def _latest(session: AsyncSession, request: Request, a: LatestArgs) -> ToolResult:
    page = await v1.v1_items(session, mode=a.mode, window=a.window, channel=Channel(a.channel) if a.channel else None,
                             q=None, cursor=None, limit=a.limit)
    label = f"{'过去 24 小时' if a.window == '24h' else '最近 7 天'}的{'精选' if a.mode == 'selected' else '全部动态'}"
    return _render_items(label, page.items), page.model_dump(mode="json")


async def _search(session: AsyncSession, request: Request, a: SearchArgs) -> ToolResult:
    found = await v1.v1_search(request, session, q=a.q, limit=a.limit)
    return _render_items(f"「{a.q}」的搜索结果", found), {"items": [i.model_dump(mode="json") for i in found]}


async def _leads(session: AsyncSession, request: Request, a: LeadsArgs) -> ToolResult:
    page = await v1.v1_leads(
        session, stage=Stage(a.stage) if a.stage else None, province=a.province, biz_line=None,
        open_only=a.open_only, min_amount_wan=Decimal(str(a.min_amount_wan)) if a.min_amount_wan is not None else None,
        min_voltage_kv=a.min_voltage_kv, q=a.q, sort=a.sort, offset=0, limit=a.limit,
    )
    text = _render_items(f"商机（共 {page.total} 条符合，显示前 {len(page.items)} 条）", page.items)
    return text, page.model_dump(mode="json")


async def _hot(session: AsyncSession, request: Request, a: HotArgs) -> ToolResult:
    stories = await v1.v1_hot_stories(session, limit=a.limit)
    if not stories:
        return "当前没有热点事件。", {"stories": []}
    text = "\n\n".join(
        f"{s.rank}. {s.title}{'（新）' if s.is_new else ''}\n   {s.source_count} 家信源 · {s.item_count} 条报道 · "
        f"story_id={s.story_id}\n   {s.url}" for s in stories
    )
    return f"当前热点（{len(stories)} 个）\n\n{text}", {"stories": [s.model_dump(mode="json") for s in stories]}


async def _story(session: AsyncSession, request: Request, a: StoryArgs) -> ToolResult:
    story = await v1.v1_story_detail(session, story_id=a.story_id)
    head = f"事件：{story.title}\n{story.source_count} 家信源 · {story.item_count} 条报道 · {story.url}"
    if story.digest:
        head += f"\n\n综述：{story.digest}"
    return f"{head}\n\n{_render_items('时间线', story.timeline)}", story.model_dump(mode="json")


def _render_knowledge(n: int, k: V1Knowledge) -> str:
    lines = [f"{n}. [{DOMAIN_LABELS[k.domain]}·{KTYPE_LABELS[k.ktype]}] {k.title}（{k.account or '未知来源'}）"]
    if k.summary:
        lines.append(f"   {k.summary}")
    lines.extend(f"   - {p}" for p in k.key_points)
    if k.standards:
        lines.append(f"   涉及标准：{'、'.join(k.standards)}")
    lines.append(f"   知识卡片：{k.url} ｜ 原文：{k.source_url}")
    return "\n".join(lines)


async def _knowledge(session: AsyncSession, request: Request, a: KnowledgeArgs) -> ToolResult:
    page = await v1.v1_knowledge_list(
        session, domain=KnowledgeDomain(a.domain) if a.domain else None,
        ktype=KnowledgeType(a.ktype) if a.ktype else None, q=a.q, sort="score", offset=0, limit=a.limit)
    if not page.items:
        return "知识库里没有符合条件的文章。", page.model_dump(mode="json")
    text = "\n\n".join(_render_knowledge(n, k) for n, k in enumerate(page.items, 1))
    return f"知识库（共 {page.total} 篇符合，显示前 {len(page.items)} 篇）\n\n{text}", page.model_dump(mode="json")


async def _daily(session: AsyncSession, request: Request, a: DailyArgs) -> ToolResult:
    kind = DigestKind(a.kind)
    d = await (v1.v1_daily(session, day=a.date, kind=kind) if a.date else v1.v1_daily_latest(session, kind=kind))
    return f"{d.markdown}\n\n站内阅读：{d.url}", d.model_dump(mode="json")


Tool = tuple[str, str, type[Args], Callable[[AsyncSession, Request, Any], Awaitable[ToolResult]]]
_TOOLS: list[Tool] = [
    ("latest", "过去 24 小时或最近 7 天的精选 / 全部动态，可按频道筛选，最多 30 条。", LatestArgs, _latest),
    ("search", "按关键词与语义搜索全部已精读的条目（项目名、业主、地区、话题），最多 20 条。", SearchArgs, _search),
    ("leads", "结构化商机：招标、中标、项目核准与规划，可按阶段、省份、金额、电压、是否截止筛选，最多 30 条。",
     LeadsArgs, _leads),
    ("hot", "当前热点事件排名（按独立信源数与时间衰减），最多 10 个；返回的 story_id 可传给 story。", HotArgs, _hot),
    ("story", "一个事件的 AI 综述与报道时间线（最多最近 50 条）。", StoryArgs, _story),
    ("daily", "最新或指定日期的日报 / 周报全文（Markdown）。", DailyArgs, _daily),
    ("knowledge", "电力基建知识库：按关键词、专业、类型查知识卡片（要点、适用场景、涉及标准），最多 20 篇。",
     KnowledgeArgs, _knowledge),
]
TOOLS: dict[str, Tool] = {t[0]: t for t in _TOOLS}


def _tool_list() -> list[dict[str, Any]]:
    out = []
    for name, desc, model, _ in TOOLS.values():
        schema = model.model_json_schema()
        schema.pop("title", None)
        out.append({"name": name, "description": desc, "inputSchema": schema,
                    "annotations": {"readOnlyHint": True, "openWorldHint": False}})
    return out


async def _call_tool(session: AsyncSession, request: Request, params: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(params.get("name", ""))
    if tool is None:
        raise JsonRpcError(-32602, f"未知工具：{params.get('name')}")
    _, _, model, fn = tool
    try:
        args = model.model_validate(params.get("arguments") or {})
        text, data = await fn(session, request, args)
    except ValidationError as exc:
        problems = [f"{'.'.join(map(str, e['loc']))} {e['msg']}" for e in exc.errors()]
        return _tool_error("参数不合法：" + "；".join(problems))
    except HTTPException as exc:
        return _tool_error(str(exc.detail))
    return {"content": [{"type": "text", "text": text}], "structuredContent": data, "isError": False}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _dispatch(session: AsyncSession, request: Request, msg: Any) -> dict[str, Any] | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    if "id" not in msg:  # 通知（如 notifications/initialized）不需要响应
        return None
    method, params, mid = msg["method"], msg.get("params") or {}, msg["id"]
    try:
        if method == "initialize":
            asked = params.get("protocolVersion")
            result: dict[str, Any] = {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": _tool_list()}
        elif method == "tools/call":
            result = await _call_tool(session, request, params)
        else:
            return _error(mid, -32601, f"不支持的方法：{method}")
    except JsonRpcError as exc:
        return _error(mid, exc.code, exc.message)
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


@router.post("/mcp", include_in_schema=False)
async def mcp(request: Request, session: Session) -> Response:
    try:
        body = json.loads(await request.body())
    except ValueError:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)
    if isinstance(body, list):  # 2025-03-26 允许批量
        replies = [r for r in [await _dispatch(session, request, m) for m in body] if r is not None]
        return JSONResponse(replies) if replies else Response(status_code=202)
    reply = await _dispatch(session, request, body)
    return JSONResponse(reply) if reply is not None else Response(status_code=202)


@router.get("/mcp", include_in_schema=False)
async def mcp_stream() -> Response:
    # 不提供服务端推送流；规范要求此时返回 405
    return Response(status_code=405, headers={"Allow": "POST"})
