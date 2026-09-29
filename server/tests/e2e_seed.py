"""端到端测试数据：写入一个独立的测试库（不要对生产库执行）。

DATABASE_URL=...powerai_e2e python -m tests.e2e_seed

内容是固定的虚构样例（标题带「示例」字样），用于前端 E2E 与界面截图；
不经过 LLM，直接写入「已精读」状态。
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine
from app.digest.builder import build_digest
from app.models import Item, Lead, Story
from app.models.enums import DigestKind
from app.seed.loader import seed_watch_rules, sync_sources

TABLES = ("gold_labels", "eval_runs", "notifications", "leads", "items", "stories", "source_runs", "sources",
          "watch_rules", "digests", "jobs", "llm_calls", "app_settings")

SAMPLES = [
    # (source_key, title, title_zh, channel, province, score, dims, summary, reason, action, lead)
    ("csg-bidding", "示例：某省电网公司2026年输电线路无人机智能巡检服务公开招标公告",
     "示例：某省输电线路无人机智能巡检服务招标，预算 1280 万", "tender", "广东", 92.4,
     (10, 9, 9, 9, 6), "某省电网公司公开招标输电线路无人机智能巡检服务，覆盖 500kV 与 220kV 线路，预算 1280.5 万元，10 月 15 日截止投标。",
     "与智能运检业务线直接对口的在招项目", "10 月 15 日前完成投标，准备无人机巡检同类业绩与资质",
     dict(project_name="2026年输电线路无人机智能巡检服务", owner="某省电网有限公司", voltage_kv=500,
          amount_wan=Decimal("1280.5"), stage="tendering", bid_no="DEMO-2026-0931", days=16,
          biz_line="inspection_ai", match_score=92)),
    ("bjx-tender", "示例：转载 某省输电线路无人机智能巡检服务招标",
     "示例：某省输电线路无人机巡检招标（媒体转载）", "tender", "广东", 71.0,
     (9, 8, 8, 8, 5), "北极星转载某省输电线路无人机巡检服务招标信息。", "同一项目的媒体报道", "",
     dict(project_name=None, owner=None, voltage_kv=None, amount_wan=None, stage="tendering",
          bid_no="DEMO-2026-0931", days=None, biz_line="inspection_ai", match_score=80)),
    ("csg-bidding", "示例：某供电局220kV变电站新建工程施工总承包中标候选人公示",
     "示例：某 220kV 变电站新建工程 EPC 中标候选人公示", "award", "广西", 84.0,
     (9, 7, 10, 8, 5), "某供电局 220kV 变电站新建工程施工总承包中标候选人公示，第一候选人为某电建公司，投标报价 8650 万元。",
     "可跟进二期扩建与分包机会", "联系第一候选人洽谈智能辅助监控分包",
     dict(project_name="220kV变电站新建工程施工总承包", owner="某供电局", voltage_kv=220,
          amount_wan=Decimal("8650"), stage="awarded", bid_no=None, days=None, biz_line="grid_epc",
          match_score=78, winner="某电建公司")),
    ("nea", "示例：国家能源局印发配电网高质量发展行动实施方案",
     "示例：能源局发布配电网高质量发展行动方案，明确数字化改造目标", "policy", None, 76.5,
     (9, 6, 9, 8, 9), "国家能源局印发配电网高质量发展行动实施方案，提出到 2027 年配电网数字化、智能化水平显著提升。",
     "配网智能化改造将带来持续的运检 AI 需求", "梳理各省配套细则出台节奏", None),
    ("csg", "示例：南方电网部署新型电力系统建设重点任务",
     "示例：南方电网部署新型电力系统建设重点任务", "company", None, 66.0,
     (8, 5, 8, 7, 7), "南方电网召开会议部署新型电力系统建设重点任务，强调提升输变电设备智能运维水平。",
     "反映南网未来投资方向", "", None),
    ("bjx-news", "示例：某省发改委核准500千伏输变电工程",
     "示例：某省核准 500kV 输变电工程，总投资约 12 亿元", "project", "云南", 80.5,
     (10, 8, 9, 7, 7), "某省发改委核准 500 千伏输变电工程，新建变电站一座、线路 120 公里，总投资约 12 亿元。",
     "项目已核准，后续将进入招标阶段", "提前对接业主了解设计与招标计划",
     dict(project_name="500千伏输变电工程", owner="某省电网公司", voltage_kv=500, amount_wan=Decimal("120000"),
          stage="approval", bid_no=None, days=None, biz_line="grid_epc", match_score=70)),
    ("bjx-news", "示例：某地电力交易中心发布现货市场结算细则",
     "示例：某地发布电力现货市场结算细则", "market", "山东", 58.0,
     (7, 3, 8, 7, 5), "某地电力交易中心发布现货市场结算细则征求意见稿。", "与业务关联较弱", "", None),
]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def main() -> None:
    assert "e2e" in settings.database_url, "只允许对名字含 e2e 的测试库执行"
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        await session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        await session.commit()
        await sync_sources(session)
        await seed_watch_rules(session)
        sources = {s.key: s for s in (await session.execute(text("SELECT id, key, tier FROM sources"))).all()}
        story = Story(key="bid:demo20260931", title=SAMPLES[0][2], first_seen_at=now, last_seen_at=now,
                      item_count=2, source_count=2, heat=19.6,
                      digest="某省电网公司正在公开招标输电线路无人机智能巡检服务，预算 1280.5 万元，10 月 15 日截止。尚未披露：标段划分、联系人。")
        session.add(story)
        await session.flush()
        for n, (key, title, title_zh, channel, prov, score, dims, summary, reason, action, lead) in enumerate(SAMPLES):
            src = sources[key]
            item = Item(
                source_id=src.id, tier=src.tier, url=f"https://example.com/demo/{n}", url_hash=_hash(f"demo{n}"),
                title=title, title_zh=title_zh, channel=channel, province=prov, summary=summary, reason=reason,
                action=action or None, tags=["示例"], status="analyzed", score=score, selected=score >= 65,
                d_relevance=dims[0], d_opportunity=dims[1], d_certainty=dims[2], d_timeliness=dims[3],
                d_impact=dims[4], first_seen_at=now - timedelta(hours=n * 3), analyzed_at=now,
                published_at=now - timedelta(hours=n * 3 + 1),
                content_text=summary * 3, story_id=story.id if n < 2 else None, is_story_lead=n != 1,
            )
            session.add(item)
            await session.flush()
            if lead is not None:
                days = lead.pop("days")
                session.add(Lead(item_id=item.id, province=prov,
                                 deadline_at=now + timedelta(days=days) if days else None, **lead))
        await session.commit()
        await build_digest(session, DigestKind.DAILY, (now + timedelta(days=1)).astimezone(settings.tz).date())
    await engine.dispose()
    print("E2E 示例数据已写入")


if __name__ == "__main__":
    asyncio.run(main())
