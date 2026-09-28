"""把 sources.yaml / defaults 同步进数据库。幂等：可在每次部署后执行。

python -m app.seed.loader
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source, WatchRule
from app.models.enums import Channel, SourceKind, Tier

SEED_DIR = Path(__file__).parent


class SourceSpec(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str
    kind: SourceKind
    url: str
    tier: Tier = Tier.T2
    category: Channel = Channel.INDUSTRY
    enabled: bool = True
    interval_min: int = Field(default=120, ge=10)
    notes: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


def load_source_specs(path: Path = SEED_DIR / "sources.yaml") -> list[SourceSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    specs = [SourceSpec.model_validate(row) for row in data]
    keys = [s.key for s in specs]
    if len(keys) != len(set(keys)):
        raise ValueError("sources.yaml 中存在重复的 key")
    return specs


async def sync_sources(session: AsyncSession, specs: list[SourceSpec] | None = None) -> int:
    """新增信源按 yaml 建；已有信源只同步定义性字段，保留设置页里改过的启停与频率。"""
    specs = specs if specs is not None else load_source_specs()
    for spec in specs:
        values = spec.model_dump(mode="json")
        stmt = insert(Source).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Source.key],
            set_={k: stmt.excluded[k] for k in ("name", "kind", "url", "tier", "category", "notes", "config")},
        )
        await session.execute(stmt)
    await session.commit()
    return len(specs)


DEFAULT_WATCH_RULES: list[dict[str, Any]] = [
    {"name": "智能运检/AI 视觉", "keywords": ["布控球", "无人机巡检", "变电站智能", "视频监控", "智能巡检",
                                          "安全帽识别", "智慧工地", "在线监测", "边缘计算", "AI识别"]},
    {"name": "输变电工程", "keywords": ["变电站新建", "输变电工程", "线路工程", "EPC", "施工总承包"],
     "min_voltage_kv": 110},
    {"name": "特高压", "keywords": ["特高压"]},
]


async def seed_watch_rules(session: AsyncSession) -> None:
    if (await session.scalars(select(WatchRule.id).limit(1))).first() is not None:
        return
    session.add_all(WatchRule(**rule) for rule in DEFAULT_WATCH_RULES)
    await session.commit()


async def main() -> None:
    from app.db import SessionLocal, engine

    async with SessionLocal() as session:
        n = await sync_sources(session)
        await seed_watch_rules(session)
    await engine.dispose()
    print(f"已同步 {n} 个信源")


if __name__ == "__main__":
    asyncio.run(main())
