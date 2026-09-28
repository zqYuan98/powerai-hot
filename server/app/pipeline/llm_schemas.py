"""LLM 输出契约。宽进严出：模型偶尔越界的值在这里被夹回合法范围或置空。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.collectors.textutil import CN_TZ
from app.models.enums import BizLine, Channel, Stage

_CHANNELS = {c.value for c in Channel}
_STAGES = {s.value for s in Stage}
_BIZ = {b.value for b in BizLine}


def _clamp(v: Any, hi: int) -> int:
    try:
        return max(0, min(hi, round(float(v))))
    except (TypeError, ValueError):
        return 0


def _channel(v: Any) -> str:
    return v if v in _CHANNELS else Channel.INDUSTRY.value


def _opt_str(v: Any, limit: int = 200) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] if s and s.lower() not in ("null", "none", "无", "未知", "未披露") else None


class ScreenRow(BaseModel):
    i: int
    relevant: bool = True
    channel: str = Channel.INDUSTRY.value
    province: str | None = None
    reason: str = ""

    @field_validator("channel", mode="before")
    @classmethod
    def _ch(cls, v: Any) -> str:
        return _channel(v)

    @field_validator("province", mode="before")
    @classmethod
    def _pv(cls, v: Any) -> str | None:
        return _opt_str(v, 16)


class ScreenOutput(BaseModel):
    results: list[ScreenRow]


class Scores(BaseModel):
    relevance: int = 0
    opportunity: int = 0
    certainty: int = 0
    timeliness: int = 0
    impact: int = 0

    @field_validator("*", mode="before")
    @classmethod
    def _range(cls, v: Any) -> int:
        return _clamp(v, 10)


class LeadOut(BaseModel):
    project_name: str | None = None
    owner: str | None = None
    province: str | None = None
    voltage_kv: int | None = None
    amount_wan: float | None = None
    stage: str = Stage.UNKNOWN.value
    bid_no: str | None = None
    deadline: datetime | None = None
    qualification: str | None = None
    winner: str | None = None
    biz_line: str = BizLine.OTHER.value
    match_score: int = 0

    @field_validator("project_name", "owner", "winner", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str | None:
        return _opt_str(v, 300)

    @field_validator("bid_no", mode="before")
    @classmethod
    def _bid(cls, v: Any) -> str | None:
        return _opt_str(v, 100)

    @field_validator("province", mode="before")
    @classmethod
    def _prov(cls, v: Any) -> str | None:
        return _opt_str(v, 16)

    @field_validator("qualification", mode="before")
    @classmethod
    def _qual(cls, v: Any) -> str | None:
        return _opt_str(v, 200)

    @field_validator("voltage_kv", "amount_wan", mode="before")
    @classmethod
    def _num(cls, v: Any) -> Any:
        if v in (None, "", "null"):
            return None
        try:
            return float(str(v).replace(",", "")) if v is not None else None
        except ValueError:
            return None

    @field_validator("deadline", mode="before")
    @classmethod
    def _deadline(cls, v: Any) -> datetime | None:
        if not v:
            return None
        text = str(v).strip()
        if text.endswith("24:00"):  # 「12月20日24时」= 次日零点
            base = LeadOut._deadline(text[:-5].strip())
            return base + timedelta(days=1) if base else None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(v).strip(), fmt).replace(tzinfo=CN_TZ)
            except ValueError:
                continue
        return None

    @field_validator("stage", mode="before")
    @classmethod
    def _stage(cls, v: Any) -> str:
        return v if v in _STAGES else Stage.UNKNOWN.value

    @field_validator("biz_line", mode="before")
    @classmethod
    def _biz(cls, v: Any) -> str:
        return v if v in _BIZ else BizLine.OTHER.value

    @field_validator("match_score", mode="before")
    @classmethod
    def _match(cls, v: Any) -> int:
        return _clamp(v, 100)


class AnalyzeOutput(BaseModel):
    title_zh: str = Field(default="", max_length=200)
    summary: str = ""
    reason: str = ""
    action: str = ""
    channel: str = Channel.INDUSTRY.value
    province: str | None = None
    tags: list[str] = Field(default_factory=list)
    event_key: str | None = None
    is_hype: bool = False
    scores: Scores = Field(default_factory=Scores)
    lead: LeadOut | None = None

    @field_validator("channel", mode="before")
    @classmethod
    def _ch(cls, v: Any) -> str:
        return _channel(v)

    @field_validator("province", mode="before")
    @classmethod
    def _pv(cls, v: Any) -> str | None:
        return _opt_str(v, 16)

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.replace("，", ",").split(",")
        return [str(t).strip()[:32] for t in (v or []) if str(t).strip()][:4]

    @field_validator("event_key", mode="before")
    @classmethod
    def _slug(cls, v: Any) -> str | None:
        s = _opt_str(v, 120)
        if not s:
            return None
        s = re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
        return s or None


class StoryDigestOutput(BaseModel):
    digest: str


class DailySection(BaseModel):
    name: str
    comment: str = ""


class DailyOutput(BaseModel):
    lead_id: int = 0
    lead_title: str = ""
    overview: str = ""
    sections: list[DailySection] = Field(default_factory=list)
