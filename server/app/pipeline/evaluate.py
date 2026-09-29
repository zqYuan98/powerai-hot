"""精选校准：分层抽取待标注条目，按人工标注评测精选的查准率与查全率，并扫描门槛。

两种评测：
- stored：直接用库里已有的判断，不花钱，反映线上当时的表现；
- rerun：用当前的提示词、模型和打分参数把标注样本重跑一遍。走的是线上同一套函数
  （screen_items / analyze_item / apply_analysis），但条目在内存里改、绝不写回。改了提示词或参数后用它对比。

先改标准再动门槛：门槛只能整体移动，解决不了「哪一类判错了」。
"""
from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.llm.client import call_tag, load_prompt
from app.models import EvalRun, GoldLabel, Item, LlmCall
from app.models.enums import ItemStatus
from app.pipeline.analyze import analyze_item, apply_analysis
from app.pipeline.process import ProcessStats, screen_items
from app.pipeline.tuning import Tuning, load_tuning

Decision = Literal["select", "reject", "either"]
Mode = Literal["stored", "rerun"]
Split = Literal["development", "holdout", "all"]

# 抽样配比：差一点入选/差一点落选的难例要多，一眼能判的放太多会让准确率虚高
STRATUM_TARGET = {"selected": 0.30, "near": 0.30, "low": 0.15, "screened": 0.25}
NEAR_MARGIN = 15.0      # 分数在「最低门槛 - 15」以上的未入选条目算难例
HOLDOUT_EVERY = 5       # item_id 能被 5 整除的进留出集（约 20%），调提示词只看开发集
SWEEP = range(40, 92, 2)
EXCLUDED_STAGES = ("failed", "unjudged")


def split_of(item_id: int) -> str:
    return "holdout" if item_id % HOLDOUT_EVERY == 0 else "development"


def _low_bar(tuning: Tuning) -> float:
    return min(tuning.thresholds.values()) - NEAR_MARGIN


def stratum_of(item: Item, tuning: Tuning) -> str:
    if item.status == ItemStatus.SCREENED_OUT:
        return "screened"
    if item.status != ItemStatus.ANALYZED:
        return "other"
    if item.selected:
        return "selected"
    return "near" if (item.score or 0) >= _low_bar(tuning) else "low"


def _stratum_where(stratum: str, tuning: Tuning) -> list[ColumnElement[bool]]:
    analyzed = Item.status == ItemStatus.ANALYZED
    low_bar = _low_bar(tuning)
    where: dict[str, list[ColumnElement[bool]]] = {
        "selected": [analyzed, Item.selected.is_(True)],
        "near": [analyzed, ~Item.selected, Item.score >= low_bar],
        "low": [analyzed, ~Item.selected, or_(Item.score < low_bar, Item.score.is_(None))],
        "screened": [Item.status == ItemStatus.SCREENED_OUT],
    }
    return where[stratum]


# ---------- 标注 ----------

async def next_case(session: AsyncSession, tuning: Tuning, skip: list[int] | None = None) -> Item | None:
    """挑下一条待标注条目：先补相对配比最欠缺的层，层内随机。"""
    labeled = dict((await session.execute(
        select(GoldLabel.stratum, func.count()).group_by(GoldLabel.stratum)
    )).all())
    order = sorted(STRATUM_TARGET, key=lambda s: labeled.get(s, 0) / STRATUM_TARGET[s])
    unlabeled = ~Item.id.in_(select(GoldLabel.item_id))
    for stratum in order:
        stmt = select(Item).where(unlabeled, *_stratum_where(stratum, tuning))
        if skip:
            stmt = stmt.where(Item.id.not_in(skip))
        if item := (await session.scalars(stmt.order_by(func.random()).limit(1))).first():
            return item
    return None


async def save_label(session: AsyncSession, item: Item, decision: Decision, note: str | None) -> GoldLabel:
    """新增或改标注。层和数据集划分以第一次标注时为准，改标注只改结论和备注。"""
    label = await session.get(GoldLabel, item.id)
    if label is None:
        label = GoldLabel(item_id=item.id, split=split_of(item.id),
                          stratum=stratum_of(item, await load_tuning(session)))
        session.add(label)
    label.decision = decision
    label.note = (note or "").strip() or None
    await session.commit()
    return label


# ---------- 指标 ----------

def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def confusion(cases: list[dict[str, Any]], predict: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    """「两可」和没判出结果的条目不计入。"""
    tp = fp = fn = tn = 0
    for c in cases:
        if c["gold"] == "either" or c["stage"] in EXCLUDED_STAGES:
            continue
        predicted, gold = predict(c), c["gold"] == "select"
        tp += predicted and gold
        fp += predicted and not gold
        fn += gold and not predicted
        tn += not gold and not predicted
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision and recall else None
    n = tp + fp + fn + tn
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "predicted": tp + fp,
            "accuracy": _ratio(tp + tn, n), "precision": precision, "recall": recall, "f1": f1}


def _current(c: dict[str, Any]) -> bool:
    return bool(c["selected"])


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by = lambda key: {  # noqa: E731
        k: confusion([c for c in cases if c[key] == k], _current) for k in sorted({c[key] for c in cases})
    }
    return {
        **confusion(cases, _current),
        "total": len(cases),
        "either": sum(c["gold"] == "either" for c in cases),
        "excluded": sum(c["stage"] in EXCLUDED_STAGES for c in cases),
        "by_stratum": by("stratum"),
        "by_channel": by("channel"),
        "by_tier": by("tier"),
    }


def sweep(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """所有档位用同一个门槛（作用在含档位系数的总分上）；规则/初筛淘汰和已过截止的始终判不选。"""
    def at(t: int) -> Callable[[dict[str, Any]], bool]:
        return lambda c: not c["forced_reject"] and c["score"] is not None and c["score"] >= t
    return [{"threshold": t, **confusion(cases, at(t))} for t in SWEEP]


def is_error(c: dict[str, Any]) -> bool:
    return c["gold"] != "either" and c["stage"] not in EXCLUDED_STAGES and c["selected"] != (c["gold"] == "select")


# ---------- 评测 ----------

def _stage(item: Item) -> str:
    if item.status == ItemStatus.SCREENED_OUT:
        return "screen" if (item.status_reason or "").startswith("初筛") else "rule"
    if item.status == ItemStatus.ANALYZED:
        return "analyzed"
    return "failed" if item.status == ItemStatus.FAILED else "unjudged"


def _case(label: GoldLabel, item: Item) -> dict[str, Any]:
    stage = _stage(item)
    analyzed = stage == "analyzed"
    return {
        "item_id": item.id, "gold": label.decision, "split": label.split, "stratum": label.stratum,
        "note": label.note, "title": item.title, "title_zh": item.title_zh, "source": item.source.name,
        "tier": item.tier, "channel": item.channel, "stage": stage,
        "score": item.score if analyzed else None,
        "selected": analyzed and item.selected,
        "forced_reject": not analyzed or item.status_reason == "已过截止时间",
        "reason": item.status_reason if not analyzed else item.reason,
        "dims": {"relevance": item.d_relevance, "opportunity": item.d_opportunity, "certainty": item.d_certainty,
                 "timeliness": item.d_timeliness, "impact": item.d_impact} if analyzed else None,
    }


def config_hash(tuning: Tuning) -> str:
    raw = "\n".join([load_prompt("screen"), load_prompt("analyze"), tuning.model_dump_json(),
                     settings.llm_model_fast, settings.analyze_model])
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


async def _load(session: AsyncSession, split: Split) -> list[tuple[GoldLabel, Item]]:
    stmt = (select(GoldLabel, Item).join(Item, Item.id == GoldLabel.item_id)
            .options(selectinload(Item.lead)).order_by(GoldLabel.item_id))
    if split != "all":
        stmt = stmt.where(GoldLabel.split == split)
    return [(g, i) for g, i in (await session.execute(stmt)).all()]


async def _rerun(split: Split, tuning: Tuning) -> list[dict[str, Any]]:
    async with SessionLocal() as scratch:  # 读完即关：条目脱离会话，之后的改动只在内存里，绝不写回
        rows = await _load(scratch, split)
    items = [item for _, item in rows]
    for item in items:
        item.status, item.status_reason, item.selected, item.score = ItemStatus.NEW.value, None, False, None
    survivors = await screen_items(items, tuning, ProcessStats(total=len(items)))
    outputs = await asyncio.gather(*(analyze_item(i, tuning.profile) for i in survivors), return_exceptions=True)
    for item, out in zip(survivors, outputs, strict=True):
        if isinstance(out, BaseException):
            item.status, item.status_reason = ItemStatus.FAILED.value, str(out)[:300]
        else:
            apply_analysis(item, out, tuning)
    return [_case(label, item) for label, item in rows]


async def run_eval(session: AsyncSession, *, mode: Mode, split: Split, label: str | None = None) -> EvalRun:
    """跑一次评测并存档。失败时记录错误、不抛出。"""
    tuning = await load_tuning(session)
    params: dict[str, Any] = {"thresholds": tuning.thresholds, "tier_coef": tuning.tier_coef}
    if mode == "rerun":
        params |= {"screen_model": settings.llm_model_fast, "analyze_model": settings.analyze_model,
                   "config_hash": config_hash(tuning), "weights": tuning.weights.model_dump()}
    run = EvalRun(label=(label or "").strip()[:100] or ("线上已有判断" if mode == "stored" else "当前配置重跑"),
                  mode=mode, split=split, params=params)
    session.add(run)
    await session.commit()
    started = datetime.now(UTC)
    token = call_tag.set("eval")
    try:
        if mode == "stored":
            cases = [_case(g, i) for g, i in await _load(session, split)]
        else:
            cases = await _rerun(split, tuning)
        run.cases, run.metrics, run.sweep = cases, summarize(cases), sweep(cases)
        run.status = "done"
    except Exception as exc:
        run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"[:1000]
    finally:
        call_tag.reset(token)
    run.cost_yuan = round(await session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_yuan), 0.0))
        .where(LlmCall.task.like("eval:%"), LlmCall.created_at >= started)
    ) or 0.0, 4)
    run.finished_at = datetime.now(UTC)
    await session.commit()
    return run


# ---------- 文本报告（命令行） ----------

def _pct(v: float | None) -> str:
    return "  - " if v is None else f"{v * 100:3.0f}%"


def format_report(run: EvalRun) -> str:
    if run.status != "done":
        return f"评测 #{run.id} 失败：{run.error}"
    m = run.metrics
    lines = [
        f"评测 #{run.id}「{run.label}」 {run.mode} · {run.split} · {m['total']} 条"
        f"（两可 {m['either']}，没判出结果 {m['excluded']}） · 花费 {run.cost_yuan:.3f} 元",
        f"当前配置：查准 {_pct(m['precision'])}  查全 {_pct(m['recall'])}  F1 {m['f1'] or '-'}  "
        f"准确率 {_pct(m['accuracy'])}（选出 {m['predicted']}，该选 {m['tp'] + m['fn']}）",
        "分层：" + "  ".join(f"{k} 判错 {v['fp'] + v['fn']}/{v['n']}" for k, v in m["by_stratum"].items()),
        "",
        "门槛扫描（所有档位同一门槛，作用在含档位系数的总分上）：",
        "  门槛  选出  查准  查全    F1",
    ]
    lines += [f"  {s['threshold']:>4}  {s['predicted']:>4}  {_pct(s['precision'])}  {_pct(s['recall'])}  "
              f"{s['f1'] if s['f1'] is not None else '-':>5}" for s in run.sweep]
    errors = sorted((c for c in run.cases if is_error(c)), key=lambda c: -(c["score"] or 0))
    lines += ["", f"判错 {len(errors)} 条："]
    for c in errors:
        kind = "多选" if c["selected"] else "漏选"
        score = f"{c['score']:.0f}" if c["score"] is not None else c["stage"]
        lines.append(f"  [{kind}] #{c['item_id']} {score:>8} {c['tier']:<4} {c['source']}｜{c['title'][:50]}")
    return "\n".join(lines)


async def label_stats(session: AsyncSession) -> dict[str, dict[str, int]]:
    async def by(col: Any) -> dict[str, int]:
        return {k: n for k, n in (await session.execute(select(col, func.count()).group_by(col))).all()}
    return {"decision": await by(GoldLabel.decision), "stratum": await by(GoldLabel.stratum),
            "split": await by(GoldLabel.split)}
