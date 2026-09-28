"""零成本规则：硬噪音拦截 + 强特征频道判定。

招标/中标/核准这类体裁有确定的标题特征，代码判定比模型稳定，因此规则优先于模型。
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from app.models.enums import Channel

POWER_KW = ("电力", "电网", "供电", "变电", "输电", "配电", "输变电", "特高压", "千伏", "kV", "KV",
            "储能", "光伏", "风电", "发电", "新能源", "能源", "国网", "南网", "电站", "线路", "巡检")

NOISE_KW = ("娱乐", "明星", "八卦", "彩票", "星座", "旅游攻略", "美食", "淘宝", "天猫", "京东", "拼多多",
            "券后", "促销", "优惠券", "双11", "双十一", "618大促",
            "食堂", "食材", "物业服务", "保洁", "法律顾问", "印刷", "办公用品", "绿化养护")

# 顺序敏感：中标类标题往往也含「招标」「采购」，必须先判
_CHANNEL_RULES: tuple[tuple[Channel, tuple[str, ...]], ...] = (
    (Channel.AWARD, ("中标", "成交", "中选", "候选人", "结果公示", "结果公告", "采购结果")),
    (Channel.TENDER, ("招标", "采购", "询价", "比选", "竞争性谈判", "竞争性磋商", "资格预审", "单一来源", "招募")),
    (Channel.PROJECT, ("核准", "可研", "开工", "投运", "投产", "并网", "批复", "备案", "环评", "竣工")),
    (Channel.PLANNING, ("规划", "十五五", "十四五", "投资计划", "白皮书", "行动方案", "路线图")),
    (Channel.MARKET, ("电价", "电力市场", "现货", "交易中心", "售电", "辅助服务", "容量电价", "绿电", "绿证")),
    (Channel.POLICY, ("政策", "发改委", "能源局", "管理办法", "实施方案", "印发", "征求意见", "条例", "细则", "指导意见")),
)


def has_power_signal(text: str) -> bool:
    return any(k in text for k in POWER_KW)


def hard_noise(title: str) -> str | None:
    """命中噪音词且没有任何电力信号 → 返回拦截原因。「某供电公司食堂采购」这类也拦。"""
    hit = next((k for k in NOISE_KW if k in title), None)
    if hit is None:
        return None
    if hit in ("食堂", "食材", "物业服务", "保洁", "法律顾问", "印刷", "办公用品", "绿化养护"):
        return f"非电力类采购：{hit}"
    return None if has_power_signal(title) else f"噪音词：{hit}"


_YEAR = re.compile(r"(20\d{2})\s*年")


def stale_title(title: str, now: datetime | None = None) -> str | None:
    """标题里出现的年份全都早于去年（如「2023年12月第2批采购」）→ 旧公告，返回原因。
    列表页常混入置顶的历史公告，且不一定带日期，这一步零成本拦截。"""
    years = [int(y) for y in _YEAR.findall(title)]
    this_year = (now or datetime.now(UTC)).year
    if years and max(years) < this_year - 1:
        return f"旧公告：标题年份 {max(years)}"
    return None


def rule_channel(title: str) -> Channel | None:
    for channel, words in _CHANNEL_RULES:
        if any(w in title for w in words):
            return channel
    return None
