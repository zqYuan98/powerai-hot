"""总分合成与精选判定：纯函数，参数全部来自 Tuning（设置页可调且真实生效）。"""
from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.tuning import Tuning


@dataclass(frozen=True)
class Dims:
    relevance: int
    opportunity: int
    certainty: int
    timeliness: int
    impact: int


def compute_score(dims: Dims, tier: str, tuning: Tuning, *, is_hype: bool = False) -> float:
    weights = tuning.weights.model_dump()
    total_w = sum(weights.values())
    base = sum(getattr(dims, k) * w for k, w in weights.items()) / total_w * 10  # 0-100
    score = base * tuning.tier_coef.get(tier, 1.0)
    if is_hype:
        score *= tuning.hype_penalty
    return round(min(score, 100.0), 1)


def is_selected(score: float, tier: str, tuning: Tuning) -> bool:
    return score >= tuning.thresholds.get(tier, max(tuning.thresholds.values()))
