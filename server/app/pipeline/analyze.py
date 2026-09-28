"""LLM① 批量初筛 + LLM② 逐条精读，以及把精读结果写回条目。"""
from __future__ import annotations

from datetime import UTC, datetime

from app.collectors.textutil import CN_TZ
from app.config import settings
from app.llm.client import complete_json, load_prompt
from app.models import Item, Lead
from app.models.enums import LEAD_CHANNELS, Channel, Stage
from app.pipeline.grounding import ground_lead
from app.pipeline.llm_schemas import AnalyzeOutput, ScreenOutput, ScreenRow
from app.pipeline.rules import rule_channel
from app.pipeline.scoring import Dims, compute_score, is_selected
from app.pipeline.tuning import Tuning

SCREEN_SNIPPET = 300
ANALYZE_BODY = 1800

_DEFAULT_STAGE = {
    Channel.TENDER: Stage.TENDERING,
    Channel.AWARD: Stage.AWARDED,
    Channel.PROJECT: Stage.UNKNOWN,
    Channel.PLANNING: Stage.PLANNING,
}


def _fmt_date(dt: datetime | None) -> str:
    return dt.astimezone(CN_TZ).strftime("%Y-%m-%d") if dt else "未知"


async def screen_batch(items: list[Item], profile: str) -> dict[int, ScreenRow]:
    """返回 {item.id: 判定}。模型漏掉的条目按「相关」处理（粗筛宁放勿杀）。"""
    lines = []
    for n, item in enumerate(items, 1):
        snippet = (item.content_text or "")[:SCREEN_SNIPPET].replace("\n", " ")
        lines.append(f"[{n}] 来源:{item.source.name} | 标题:{item.title}" + (f" | 摘要:{snippet}" if snippet else ""))
    out = await complete_json(
        task="screen",
        model=settings.llm_model_fast,
        system=load_prompt("screen").replace("{profile}", profile),
        user="\n".join(lines),
        schema=ScreenOutput,
        max_tokens=150 + 60 * len(items),
        temperature=0.1,
    )
    by_index = {row.i: row for row in out.results}
    return {
        item.id: by_index.get(n, ScreenRow(i=n, relevant=True, channel=item.channel))
        for n, item in enumerate(items, 1)
    }


def build_analyze_input(item: Item) -> str:
    body = (item.content_text or "").strip()
    return "\n".join([
        f"今天：{datetime.now(CN_TZ):%Y-%m-%d}",
        f"来源：{item.source.name}（档位 {item.tier}）",
        f"发布时间：{_fmt_date(item.published_at)}",
        f"频道提示：{item.channel}",
        f"标题：{item.title}",
        f"正文：{body[:ANALYZE_BODY] if body else '（仅有标题，无正文）'}",
    ])


async def analyze_item(item: Item, profile: str) -> AnalyzeOutput:
    return await complete_json(
        task="analyze",
        model=settings.analyze_model,
        system=load_prompt("analyze").replace("{profile}", profile),
        user=build_analyze_input(item),
        schema=AnalyzeOutput,
        max_tokens=1500,
        temperature=0.2,
    )


def apply_analysis(item: Item, out: AnalyzeOutput, tuning: Tuning) -> Lead | None:
    """把精读结果写回条目（不提交）。返回需要保存的 Lead（非商机频道返回 None）。"""
    channel = rule_channel(item.title) or Channel(out.channel)
    item.channel = channel.value
    item.title_zh = out.title_zh.strip() or None
    item.summary = out.summary.strip() or None
    item.reason = out.reason.strip() or None
    item.action = out.action.strip() or None
    item.province = out.province or (out.lead.province if out.lead else None)
    item.tags = out.tags
    item.event_key = out.event_key
    s = out.scores
    item.d_relevance, item.d_opportunity, item.d_certainty = s.relevance, s.opportunity, s.certainty
    item.d_timeliness, item.d_impact = s.timeliness, s.impact
    item.score = compute_score(Dims(**s.model_dump()), item.tier, tuning, is_hype=out.is_hype)
    item.selected = is_selected(item.score, item.tier, tuning)
    item.status = "analyzed"
    item.status_reason = "包装大于实质" if out.is_hype else None
    item.analyzed_at = datetime.now(UTC)

    if channel not in LEAD_CHANNELS:
        return None
    raw = out.lead.model_dump() if out.lead else {}
    raw["deadline_at"] = raw.pop("deadline", None)
    source_text = f"{item.title}\n{item.content_text or ''}"
    grounded = ground_lead(raw, source_text)
    v = grounded.values
    lead = item.lead or Lead(item_id=item.id)
    lead.project_name = v.get("project_name")  # type: ignore[assignment]
    lead.owner = v.get("owner")  # type: ignore[assignment]
    lead.bid_no = v.get("bid_no")  # type: ignore[assignment]
    lead.winner = v.get("winner")  # type: ignore[assignment]
    lead.amount_wan = v.get("amount_wan")  # type: ignore[assignment]
    lead.voltage_kv = v.get("voltage_kv")  # type: ignore[assignment]
    lead.deadline_at = v.get("deadline_at")  # type: ignore[assignment]
    lead.province = item.province
    lead.qualification = raw.get("qualification")
    stage = raw.get("stage") or Stage.UNKNOWN.value
    lead.stage = stage if stage != Stage.UNKNOWN.value else _DEFAULT_STAGE.get(channel, Stage.UNKNOWN).value
    lead.biz_line = raw.get("biz_line") or "other"
    lead.match_score = int(raw.get("match_score") or 0)
    lead.dropped_fields = grounded.dropped
    return lead

