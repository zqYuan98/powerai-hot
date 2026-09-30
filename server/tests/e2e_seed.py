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
from app.models import Article, Item, Lead, Story
from app.models.enums import DigestKind
from app.seed.loader import seed_watch_rules, sync_sources

TABLES = ("articles", "feedback", "gold_labels", "eval_runs", "notifications", "leads", "items", "stories", "source_runs", "sources",
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


ARTICLES = [
    # (account, title, title_zh, domain, ktype, score, dims, summary, points, scenarios, solution_use, standards)
    ("示例·送变电", "干货！GIS 安装的 8 个关键控制点，建议收藏", "示例：GIS 安装的 8 个质量控制点", "substation",
     "construction", 80.5, (8, 9, 8, 6), "按工序梳理 GIS 从基础复测到气体试验的关键控制点与验收指标。",
     ["基础预埋件水平误差不大于 2mm，安装前复测", "对接前清洁法兰面，环境湿度不超过 80%，搭设防尘棚",
      "SF6 气体含水量交接试验值小于 150μL/L", "抽真空保持时间与真空度按厂家文件执行并记录"],
     "变电站 GIS 安装施工、监理旁站与验收", "施工组织设计的质量控制章节、监理细则",
     ["GB 50147-2010", "GB 50150-2016"]),
    ("示例·电力方案库", "输电线路无人机自主巡检系统建设方案（附架构图）", "示例：输电线路无人机自主巡检系统的建设方案思路",
     "inspection", "design", 76.0, (8, 8, 7, 7), "从机巢布点、航线规划到缺陷识别闭环，给出一套可复用的建设方案框架。",
     ["机巢按 15–20km 巡检半径布点，优先覆盖重要交叉跨越", "航线由激光点云自动生成，杆塔精细化巡检 8–12 个拍摄点",
      "缺陷识别模型输出进入工单系统，形成发现—派单—消缺闭环"],
     "地市供电公司输电运检智能化改造", "智能运检类投标技术方案的总体架构与实施路径", []),
    ("示例·电力图书馆", "接地电阻为什么总测不合格？五种降阻方法对比", "示例：接地网降阻的五种做法与适用条件", "civil",
     "principle", 68.0, (7, 7, 7, 6), "对比深井接地、外引接地、降阻剂等五种降阻方式的原理、成本与适用地质。",
     ["高土壤电阻率地区优先深井接地，井深以穿透高阻层为准", "降阻剂需选用长效型，注意对接地体的腐蚀性",
      "外引接地距离受限于接地体有效长度"],
     "山区、岩石地区变电站与杆塔接地施工", "", ["GB/T 50065-2011"]),
]


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
        for n, (account, title, title_zh, domain, ktype, score, dims, summary, points, scen, use, stds) in \
                enumerate(ARTICLES):
            session.add(Article(
                url=f"https://example.com/knowledge/{n}", url_hash=_hash(f"knowledge{n}"), account=account,
                title=title, title_zh=title_zh, status="analyzed", domain=domain, ktype=ktype, score=score,
                d_depth=dims[0], d_practical=dims[1], d_accuracy=dims[2], d_original=dims[3], summary=summary,
                key_points=points, scenarios=scen, solution_use=use or None, standards=stds, tags=["示例"],
                content_text="\n".join(points), published_at=now - timedelta(days=n + 2), analyzed_at=now,
            ))
        await session.commit()
        await build_digest(session, DigestKind.DAILY, (now + timedelta(days=1)).astimezone(settings.tz).date())
    await engine.dispose()
    print("E2E 示例数据已写入")


if __name__ == "__main__":
    asyncio.run(main())
