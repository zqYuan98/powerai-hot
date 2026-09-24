"""周报与主题研报（writer 角色）——长文综合是唯一该用生成模型的聚合场景。

后台任务自开会话（session_factory 可测试注入，同 services/cards.py 模式）；
stub 模式退化为代码拼装的素材清单 markdown，链路可离线跑通。
联网检索为 spec 中的可配置项，默认关闭，本版仅库内检索。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from analyzer.base import get_analyzer
from analyzer.embedder import embed
from core.sqlutil import escape_like
from models import schema
from models.database import SessionLocal
from services.clustering import cosine, utcnow

log = logging.getLogger("research")

session_factory = SessionLocal

WEEKLY_SYSTEM = (
    "你是电力基建行业 AI 算法负责人的私人研究助理。基于给定素材撰写周报，"
    "markdown 格式，结构：## 本周要闻（3-5条，每条一句话点评）、## 论文与技术趋势、"
    "## 行业与国网动向、## 值得跟进的方向（结合视觉/OCR/电力场景给行动建议）。"
    "只依据素材，不要编造；引用条目附素材中的链接。中文，1000字以内。"
)

TOPIC_SYSTEM = (
    "你是电力基建行业 AI 算法负责人的私人研究助理。基于给定素材就主题撰写研究报告，"
    "markdown 格式，结构：## 背景、## 现状与关键进展、## 关键玩家、## 技术路线、"
    "## 机会与风险、## 参考条目（列出素材链接）。素材不足的部分明确说明，不要编造。"
    "中文，1500字以内。"
)


def _fmt(a: schema.Article) -> str:
    title = (a.meta or {}).get("title_zh") or a.title
    return (f"- [{a.channel}|{a.relevance_score}分] {title}\n"
            f"  摘要: {a.summary or '无'}\n  链接: {a.url or '无'}")


def _fallback_md(header: str, arts: list[schema.Article]) -> str:
    lines = [f"# {header}", "", "（未接入生成模型，以下为素材清单）", ""]
    lines += [_fmt(a) for a in arts]
    return "\n".join(lines)


# ---------- 周报 ----------

def _weekly_materials(db: Session) -> list[schema.Article]:
    since = utcnow() - timedelta(days=7)
    rows = db.scalars(
        select(schema.Article)
        .where(
            schema.Article.curated.is_(True),
            schema.Article.is_cluster_main.isnot(False),
            schema.Article.crawled_at >= since,
        )
        .order_by(schema.Article.relevance_score.desc())
    ).all()
    by_ch: dict[str, int] = {}
    picked: list[schema.Article] = []
    for a in rows:  # 每频道≤8条，总量≤40，控制提示词长度
        if by_ch.get(a.channel, 0) >= 8:
            continue
        by_ch[a.channel] = by_ch.get(a.channel, 0) + 1
        picked.append(a)
        if len(picked) >= 40:
            break
    return picked


def _week_title(now: datetime) -> str:
    """ISO 自然周作幂等键：同一周内不同日触发复用同一份周报。"""
    iso = now.isocalendar()
    return f"周报 · {iso[0]} 第{iso[1]:02d}周"


def create_weekly(db: Session) -> schema.Report:
    """建（或复用本自然周的）周报行并置「生成中」；生成由调用方派后台任务。"""
    title = _week_title(datetime.now())
    report = db.scalar(
        select(schema.Report).where(schema.Report.type == "weekly", schema.Report.title == title)
    )
    if report is None:
        report = schema.Report(type="weekly", title=title)
        db.add(report)
    report.status = "生成中"
    report.period_start = utcnow() - timedelta(days=7)
    report.period_end = utcnow()
    db.commit()
    return report


def generate_weekly(report_id: int) -> None:
    """后台任务：素材→writer 生成→回写；异常置「失败」不上抛。"""
    db = session_factory()
    try:
        report = db.get(schema.Report, report_id)
        if report is None:
            return
        try:
            arts = _weekly_materials(db)
            material = "\n".join(_fmt(a) for a in arts) or "（本周暂无精选素材）"
            raw = get_analyzer(task="writer").complete(
                WEEKLY_SYSTEM, f"素材（近7天精选）：\n{material}", max_tokens=2200)
            report.content_md = _fallback_md(report.title, arts) if "stub]" in raw else raw.strip()
            report.status = "完成"
        except Exception as e:
            log.warning("周报生成失败 report_id=%s: %s", report_id, e)
            report.status = "失败"
        db.commit()
    finally:
        db.close()


# ---------- 主题研报 ----------

def _topic_materials(db: Session, topic: str) -> list[schema.Article]:
    """关键词 LIKE + embedding 余弦 TopK，去重合并，≤30 条。"""
    like = f"%{escape_like(topic)}%"
    kw = db.scalars(
        select(schema.Article)
        .where(or_(schema.Article.title.ilike(like, escape="\\"),
                   schema.Article.summary.ilike(like, escape="\\")))
        .order_by(schema.Article.relevance_score.desc())
        .limit(20)
    ).all()

    sem: list[schema.Article] = []
    try:
        qv = embed(topic)
    except Exception:
        qv = None
    if qv:
        cands = db.scalars(
            select(schema.Article).where(schema.Article.embedding.isnot(None))
        ).all()
        ranked = sorted(
            ((cosine(qv, c.embedding), c) for c in cands if c.embedding),
            key=lambda t: -t[0],
        )
        sem = [c for s, c in ranked[:20] if s >= 0.35]

    seen: set[int] = set()
    out: list[schema.Article] = []
    for a in kw + sem:
        if a.id not in seen:
            seen.add(a.id)
            out.append(a)
    return out[:30]


def create_topic(db: Session, topic: str) -> schema.Report:
    report = schema.Report(type="topic", topic=topic, title=f"研报 · {topic}", status="生成中")
    db.add(report)
    db.commit()
    return report


def generate_topic(report_id: int) -> None:
    """后台任务：检索选材→writer 生成→回写；异常置「失败」不上抛。"""
    db = session_factory()
    try:
        report = db.get(schema.Report, report_id)
        if report is None:
            return
        try:
            arts = _topic_materials(db, report.topic or "")
            material = "\n".join(_fmt(a) for a in arts) or "（库内暂无相关素材）"
            raw = get_analyzer(task="writer").complete(
                TOPIC_SYSTEM, f"主题：{report.topic}\n素材：\n{material}", max_tokens=2600)
            report.content_md = _fallback_md(report.title, arts) if "stub]" in raw else raw.strip()
            report.status = "完成"
        except Exception as e:
            log.warning("研报生成失败 report_id=%s: %s", report_id, e)
            report.status = "失败"
        db.commit()
    finally:
        db.close()
