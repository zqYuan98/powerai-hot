"""今日精选日报（零 LLM）：近 24h 精选主条 → 版块分桶 → 质量分排序。

翻译/摘要/推荐理由在入库时已生成，这里只做分桶排序，秒级完成。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import schema
from services.clustering import utcnow

# 版块 → 频道映射（8 频道全覆盖；AI洞察 并入行业版块，见计划约定）
SECTIONS: list[tuple[str, list[str]]] = [
    ("论文研究", ["前沿论文"]),
    ("大模型动态", ["大模型动态"]),
    ("行业·国网动态", ["行业动态", "国网规划", "AI洞察"]),
    ("招标商机", ["招标公告"]),
    ("政策法规", ["政策法规"]),
    ("落地案例", ["落地案例"]),
]


def build_daily_digest(db: Session, now: datetime | None = None) -> schema.Report:
    now = now or datetime.now()          # 本地时间：只用于标题日期
    window_end = utcnow()                # crawled_at 是 UTC，窗口必须同时钟
    window_start = window_end - timedelta(hours=24)
    rows = db.scalars(
        select(schema.Article)
        .where(
            schema.Article.curated.is_(True),
            schema.Article.is_cluster_main.isnot(False),
            schema.Article.crawled_at >= window_start,
        )
        .order_by(schema.Article.relevance_score.desc())
    ).all()

    sections = []
    threads = list(db.scalars(
        select(schema.ResearchThread)
        .where(schema.ResearchThread.status == "active")
        .order_by(schema.ResearchThread.id)
    ))
    if threads:
        for thread in threads:
            ids = [article.id for article in rows if article.primary_thread_id == thread.id][:3]
            if ids:
                sections.append({"name": thread.name, "article_ids": ids})
        horizon_ids = [article.id for article in rows if article.primary_thread_id is None][:3]
        if horizon_ids:
            sections.append({"name": "视野", "article_ids": horizon_ids})
    else:
        for name, channels in SECTIONS:
            ids = [a.id for a in rows if a.channel in channels]
            if ids:
                sections.append({"name": name, "article_ids": ids})

    title = f"今日精选 · {now:%Y-%m-%d}"
    report = db.scalar(
        select(schema.Report).where(schema.Report.type == "daily", schema.Report.title == title)
    )
    if report is None:
        report = schema.Report(type="daily", title=title)
        db.add(report)
    report.content_json = {
        "sections": sections,
        "total": sum(len(s["article_ids"]) for s in sections),
    }
    report.period_start = window_start
    report.period_end = window_end
    report.status = "完成"
    db.commit()
    return report
