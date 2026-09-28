"""商机字段的 grounding 校验（代码实现，不靠模型自证）。

模型抽取的项目名/业主/编号/中标人/金额/电压/截止日必须能在原文中找到依据，
找不到就置空并记入 dropped_fields——宁缺毋滥，错误的金额或截止日比没有更糟。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

_WS = re.compile(r"[\s　]+")
_NUM = re.compile(r"\d+(?:\.\d+)?")


_ORG_SUFFIX = re.compile(r"(股份有限公司|有限责任公司|有限公司|集团公司|公司)$")
_ORG_ADMIN = re.compile(r"(?<=[一-龥]{2})(省|市|自治区)")


def _norm(text: str) -> str:
    return _WS.sub("", text).replace("（", "(").replace("）", ")").casefold()


def _org_core(name: str) -> str:
    """机构名主干：模型常把「国网江苏电力」补全成「国网江苏省电力有限公司」，这不算编造。"""
    return _ORG_ADMIN.sub("", _ORG_SUFFIX.sub("", _norm(name)))


def _org_grounded(name: str, norm_text: str) -> bool:
    core = _org_core(name)
    return len(core) >= 4 and (core in norm_text or core in _ORG_ADMIN.sub("", norm_text))


@dataclass
class GroundingResult:
    values: dict[str, object]
    dropped: list[str] = field(default_factory=list)


def _numbers(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for raw in _NUM.findall(text.replace(",", "").replace("，", "")):
        try:
            out.append(Decimal(raw))
        except InvalidOperation:
            continue
    return out


def _amount_grounded(amount_wan: Decimal, numbers: list[Decimal]) -> bool:
    """原文金额可能写成 元 / 万元 / 亿元，任一换算吻合即可（容差 0.5%）。"""
    for n in numbers:
        for candidate in (n, n / 10000, n * 10000):
            if candidate and abs(candidate - amount_wan) <= abs(amount_wan) * Decimal("0.005"):
                return True
    return False


def _date_grounded(dt: datetime, text: str) -> bool:
    y, m, d = dt.year, dt.month, dt.day
    variants = (
        f"{y}-{m:02d}-{d:02d}", f"{y}-{m}-{d}", f"{y}/{m}/{d}", f"{y}/{m:02d}/{d:02d}",
        f"{y}年{m}月{d}日", f"{y}年{m:02d}月{d:02d}日", f"{m}月{d}日", f"{y}.{m:02d}.{d:02d}",
    )
    return any(v in text for v in variants)


def ground_lead(lead: dict[str, object], source_text: str) -> GroundingResult:
    text = source_text or ""
    norm_text = _norm(text)
    values = dict(lead)
    dropped: list[str] = []

    def drop(name: str) -> None:
        values[name] = None
        dropped.append(name)

    for name in ("project_name", "owner", "bid_no", "winner"):
        v = values.get(name)
        if isinstance(v, str) and v.strip():
            exact = _norm(v) in norm_text
            if not exact and not (name in ("owner", "winner") and _org_grounded(v, norm_text)):
                drop(name)
        else:
            values[name] = None

    amount = values.get("amount_wan")
    if amount is not None:
        try:
            amt = Decimal(str(amount))
        except InvalidOperation:
            drop("amount_wan")
        else:
            if amt <= 0 or not _amount_grounded(amt, _numbers(text)):
                drop("amount_wan")
            else:
                values["amount_wan"] = amt

    kv = values.get("voltage_kv")
    if kv is not None:
        try:
            kv_int = int(str(kv))
        except ValueError:
            drop("voltage_kv")
        else:
            pattern = re.compile(rf"(?<!\d){kv_int}\s*(?:kv|千伏)", re.IGNORECASE)
            if not pattern.search(text):
                drop("voltage_kv")
            else:
                values["voltage_kv"] = kv_int

    deadline = values.get("deadline_at")
    if isinstance(deadline, datetime) and not _date_grounded(deadline, text):
        drop("deadline_at")

    return GroundingResult(values=values, dropped=dropped)
