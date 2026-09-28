"""业务可调参数（存 app_settings 表，设置页修改后下一条立即生效）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting

DEFAULT_PROFILE = """\
公司定位：电力基建领域的集成商，全国范围承接业务。
业务线 1 —— 智能运检 / AI 视觉：输电线路与变电站的无人机巡检、布控球与视频监控、在线监测、施工现场安监识别（安全帽/违章/入侵）、边缘计算终端与 AI 识别平台。
业务线 2 —— 输变电工程施工 / EPC：110kV 及以上变电站新建扩建、输电线路、配网改造工程的施工总承包与 EPC。
最关心：国网/南网及省公司、发电集团、地方政府的相关招标采购与中标结果；变电站/线路项目的核准、可研与开工（可提前介入）；电网投资规划与数字化/智能化政策。"""


class DimWeights(BaseModel):
    relevance: float = 0.30
    opportunity: float = 0.30
    certainty: float = 0.15
    timeliness: float = 0.10
    impact: float = 0.15

    @model_validator(mode="after")
    def _positive(self) -> DimWeights:
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("权重之和必须大于 0")
        return self


class Tuning(BaseModel):
    profile: str = DEFAULT_PROFILE
    focus: str = "智能运检/AI 视觉、输变电工程 EPC"  # 日报读者关注点（一句话）
    weights: DimWeights = Field(default_factory=DimWeights)
    tier_coef: dict[str, float] = Field(default_factory=lambda: {"T1": 1.2, "T1_5": 1.1, "T2": 1.0})
    # 进精选的分数门槛（按信源档位；档位越低门槛越高）
    thresholds: dict[str, float] = Field(default_factory=lambda: {"T1": 60.0, "T1_5": 65.0, "T2": 70.0})
    hype_penalty: float = 0.7        # 「包装大于实质」的分数系数
    lead_notify_min_match: int = 60  # 商机匹配度达到此值即推送（即使未进精选）
    story_similarity: float = 0.86   # 向量归并阈值（余弦相似度）


KEY = "tuning"


async def load_tuning(session: AsyncSession) -> Tuning:
    row = await session.get(AppSetting, KEY)
    return Tuning.model_validate(row.value) if row and row.value else Tuning()


async def save_tuning(session: AsyncSession, tuning: Tuning) -> None:
    row = await session.get(AppSetting, KEY)
    value = tuning.model_dump(mode="json")
    if row is None:
        session.add(AppSetting(key=KEY, value=value))
    else:
        row.value = value
    await session.commit()
