"""评分配置的读写与全库重算（纯代码，不调模型）。

配置整体存 scoring_config 表的单行（key="scoring"），与 DEFAULT_CONFIG 合并后生效。
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from analyzer.scoring import DEFAULT_CONFIG, evaluate
from models import schema

_ROW_KEY = "scoring"
_ALLOWED_KEYS = set(DEFAULT_CONFIG.keys())
# 键 → (取值下限, 上限)。字典型配置对每个子值套用同一范围。
_NUMERIC_RANGE = {
    "dim_weights": (0, 1000),
    "tier_coeff": (0, 10),
    "kind_coeff": (0, 10),
    "channel_thresholds": (0, 100),
    "hot_score": (0, 100),
    "cluster_threshold": (0, 1),
    "axis_threshold": (0, 100),
    "cross_threshold": (0, 100),
    "cross_quality_floor": (0, 100),
}


def _check_number(key: str, value, lo: float, hi: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} 必须是数值，收到 {value!r}")
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{key} 不能是 NaN/Inf")
    if not (lo <= value <= hi):
        raise ValueError(f"{key} 超出范围 [{lo}, {hi}]：{value}")


def _validate_updates(updates: dict) -> None:
    for key, val in updates.items():
        lo, hi = _NUMERIC_RANGE.get(key, (None, None))
        if lo is None:
            continue
        if isinstance(DEFAULT_CONFIG.get(key), dict):
            if not isinstance(val, dict):
                raise ValueError(f"{key} 必须是对象")
            # 子键也要查白名单：顶层键早有 _ALLOWED_KEYS 把关，子键没有的话，
            # 一个拼错的维度名（或 P2 之前的 relevance）会返回 200 然后被读取端
            # 静默丢弃——调用方以为改生效了，实际什么都没发生。
            unknown = set(val) - set(DEFAULT_CONFIG[key])
            if unknown:
                raise ValueError(f"{key} 含未知项: {sorted(unknown)}")
            for sub_k, sub_v in val.items():
                _check_number(f"{key}.{sub_k}", sub_v, lo, hi)
        else:
            _check_number(key, val, lo, hi)


def get_scoring_config(db: Session) -> dict:
    """读配置：与 put_scoring_config 用同一套嵌套合并规则。

    字典型配置逐键合并、不整体替换，同时丢弃 DEFAULT_CONFIG 里已不存在的键。
    两件事都是为了挡住同一类静默降级 —— 以 P2 把 `relevance` 拆成
    `ai_relevance` / `power_relevance` 为例，一行 P2 之前存下的 `dim_weights`：

      缺键不补 → 两个新维度权重为 0（compute_quality 按 weights.items() 加权，
                 缺键即完全不计入），双轴对 quality 彻底失效；
      旧键不删 → 废弃的 `relevance` 仍占 30 权重却匹配不到任何维度值（_dim 返回
                 0），只推高 total_w 分母，把加权均值整体稀释约 23%。

    两种都不报错、不留痕迹，只是分数悄悄变低。读写口径必须一致。
    """
    row = db.get(schema.ScoringConfig, _ROW_KEY)
    stored = row.value if row else {}
    merged = {**DEFAULT_CONFIG, **{k: v for k, v in stored.items() if k in DEFAULT_CONFIG}}
    for key, default in DEFAULT_CONFIG.items():
        if isinstance(default, dict) and isinstance(stored.get(key), dict):
            merged[key] = {**default, **{k: v for k, v in stored[key].items() if k in default}}
    return merged


def put_scoring_config(db: Session, updates: dict) -> dict:
    unknown = set(updates) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f"未知配置项: {sorted(unknown)}")
    _validate_updates(updates)  # 值类型/范围校验，防投毒与 UI 空字段 NaN
    row = db.get(schema.ScoringConfig, _ROW_KEY)
    if row is None:
        row = schema.ScoringConfig(key=_ROW_KEY, value={})
        db.add(row)
    # 字典型配置做嵌套合并（以默认值为底），允许只传部分频道/维度而不丢其余项
    merged = dict(row.value)
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(DEFAULT_CONFIG.get(k), dict):
            merged[k] = {**DEFAULT_CONFIG[k], **merged.get(k, {}), **v}
        else:
            merged[k] = v
    row.value = merged
    db.commit()
    return get_scoring_config(db)


def recompute_all(db: Session) -> dict:
    """对所有已评分文章用当前配置重算质量分/精选/热点。改权重后调用，秒级。

    必须和 services/ingest.py 的落库口径完全一致：有激活的研究方向时，
    relevance_score 用 learn_score（研究方向加权），否则用 quality。
    否则同一列会混进两把尺子——重算过的文章用 quality、新采集的用 learn_score，
    信息流按该列排序就会出现不可解释的顺序。
    """
    # 延迟导入：ingest 在模块级 import config_store，顶层引用会形成循环
    from services.ingest import _apply_thread_score

    cfg = get_scoring_config(db)
    threads = list(db.scalars(
        select(schema.ResearchThread)
        .where(schema.ResearchThread.status == "active")
        .order_by(schema.ResearchThread.id)
    ))
    n = 0
    for a in db.scalars(select(schema.Article).where(schema.Article.scored.is_(True))):
        if not a.dim_scores:
            continue
        verdict = evaluate(a.dim_scores, tier=a.tier or "T2", kind=a.kind or "资讯",
                           channel=a.channel, config=cfg)
        a.cross_score = verdict["cross_score"]
        a.axis = verdict["axis"]
        if threads:
            a.relevance_score = _apply_thread_score(a, {"dims": a.dim_scores}, threads, cfg)
            a.hot = a.relevance_score >= cfg["hot_score"]
        else:
            a.relevance_score = verdict["quality"]
            a.curated = verdict["curated"]
            a.hot = verdict["hot"]
        if a.noise_reason is not None or a.scored_by == "rule":
            a.curated = False
            a.hot = False
        n += 1
    db.commit()
    return {"recomputed": n}
