from __future__ import annotations

import re
from dataclasses import dataclass

from models import schema


@dataclass(frozen=True)
class ThreadScore:
    primary_thread_id: int | None
    thread_score: int
    learn_score: int


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def keyword_affinity(title: str, summary: str | None, content: str | None, threads: list[schema.ResearchThread]) -> dict[str, int]:
    text = " ".join((title or "", summary or "", (content or "")[:600]))
    normalized = re.sub(r"\s+", " ", text.casefold())
    affinity: dict[str, int] = {}
    for thread in threads:
        if thread.status != "active":
            continue
        hits = {keyword.casefold() for keyword in (thread.keywords or []) if keyword.casefold() in normalized}
        if hits:
            affinity[str(thread.id)] = min(100, 25 + 25 * len(hits))
    return affinity


def score_for_threads(
    dims: dict,
    affinity: dict,
    threads: list[schema.ResearchThread],
    *,
    tier: str,
    kind: str,
    tier_coeff: dict[str, float] | None = None,
    kind_coeff: dict[str, float] | None = None,
) -> ThreadScore:
    tier_multiplier = (tier_coeff or {"T1": 1.0, "T1.5": 0.85, "T2": 0.7}).get(tier, 0.7)
    kind_multiplier = (kind_coeff or {}).get(kind, 1.0)
    candidates: list[tuple[float, int]] = []
    for thread in threads:
        if thread.status != "active":
            continue
        raw = affinity.get(str(thread.id), affinity.get(thread.id, 0))
        candidates.append((max(0, min(100, int(raw))) * thread.weight, thread.id))
    if candidates:
        weighted, primary_id = max(candidates, key=lambda item: (item[0], -item[1]))
        thread_score = _clamp(weighted)
    else:
        primary_id, thread_score = None, 0
    base = (
        0.50 * thread_score
        + 0.20 * max(0, min(100, int(dims.get("utility", 0))))
        + 0.15 * max(0, min(100, int(dims.get("depth", 0))))
        + 0.15 * max(0, min(100, int(dims.get("firsthand", 0))))
    )
    return ThreadScore(primary_id, thread_score, _clamp(base * tier_multiplier * kind_multiplier))
