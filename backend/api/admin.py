"""管理后台 — AI 模型切换 + 调用量监控 + 立即采集 + 流水线全景状态。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session

from analyzer.summarizer import summarize
from core.rate_limit import enforce_rate_limit
from core.runtime import runtime
from models import schema
from models.database import get_db
from jobs.queue import enqueue_job
from scheduler.monitor import monitor_status
from services.config_store import get_scoring_config, put_scoring_config, recompute_all
from services.ingest import (
    BUILTIN_SOURCE_NAMES,
    count_unscored_backlog,
    ingest_once,
    source_is_crawlable,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _axis_flag(axis: str):
    """按轴计数的 0/1 表达式；SQLite 与 PG 通用（避免 FILTER 语法差异）。"""
    return case((schema.Article.axis == axis, 1), else_=0)

# 估算单价（演示用，元/千 tokens）。生产应来自配置/计费 API。
# custom 单价随供应商而异，此处按 0 计，前端单独标注「按供应商计费」。
_PRICE_PER_1K = {"deepseek": 0.001, "custom": 0.0, "ollama": 0.0}


class ProviderUpdate(BaseModel):
    provider: str
    task_providers: dict[str, str] | None = None


class TestRequest(BaseModel):
    text: str = "国家电网启动新一批特高压直流工程，将大规模部署布控球与边缘 AI 终端。"


@router.get("/config")
def get_config():
    snap = runtime.snapshot()
    # 附带费用估算
    cost = {}
    for provider, u in snap["usage"].items():
        cost[provider] = round(u["tokens"] / 1000 * _PRICE_PER_1K.get(provider, 0), 4)
    snap["estimated_cost_cny"] = cost
    snap["price_per_1k_cny"] = _PRICE_PER_1K
    return snap


@router.put("/config")
def update_config(payload: ProviderUpdate):
    try:
        runtime.set_provider(payload.provider)
        if payload.task_providers is not None:
            runtime.task_providers = {k: v.lower() for k, v in payload.task_providers.items()}
    except ValueError as e:
        raise HTTPException(400, str(e))
    return get_config()


@router.post("/test")
def test_model(payload: TestRequest):
    """用当前模型跑一次摘要，验证连通并累加调用量。"""
    result = summarize(payload.text)
    return {"provider": runtime.provider, "result": result}


class CrawlRequest(BaseModel):
    limit: int = 15
    group: str = "all"


@router.post("/crawl", status_code=202)
def crawl_now(payload: CrawlRequest, request: Request, db: Session = Depends(get_db)):
    """将人工采集持久化入队，立即返回可轮询的任务地址。"""
    enforce_rate_limit(request, "admin.crawl")
    limit = max(1, min(payload.limit, 50))
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    job = enqueue_job(
        db,
        "manual_crawl",
        {"limit": limit, "group": payload.group},
        idempotency_key=f"manual-crawl:{payload.group}:{bucket}",
        priority=20,
        created_by="admin",
    )
    return {"status": job.status, "job_id": job.id, "status_url": f"/api/admin/jobs/{job.id}"}


@router.get("/crawl/status")
def crawl_status(db: Session = Depends(get_db)):
    """返回最近一次人工采集持久任务的状态。"""
    job = db.scalar(
        select(schema.PersistentJob)
        .where(schema.PersistentJob.job_type == "manual_crawl")
        .order_by(schema.PersistentJob.id.desc())
        .limit(1)
    )
    if job is None:
        return {"status": "idle", "stats": None, "error": None}
    return {
        "status": job.status,
        "stats": job.result_json,
        "error": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "group": (job.payload_json or {}).get("group"),
        "job_id": job.id,
        "status_url": f"/api/admin/jobs/{job.id}",
    }


@router.get("/monitor")
def get_monitor():
    """定时监控状态（是否开启、间隔、上次自动采集结果）。"""
    return monitor_status()


@router.get("/scoring")
def get_scoring(db: Session = Depends(get_db)):
    """当前评分配置（六维权重/tier系数/kind系数/分频道阈值/双轴阈值/hot线）。"""
    return get_scoring_config(db)


@router.put("/scoring")
def put_scoring(payload: dict, db: Session = Depends(get_db)):
    try:
        return put_scoring_config(db, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/scoring/recompute")
def scoring_recompute(db: Session = Depends(get_db)):
    """改配置后全库纯代码重算（不调模型，秒级）。"""
    return recompute_all(db)


@router.post("/weekly")
def weekly_now(
    request: Request,
    db: Session = Depends(get_db),
):
    """立即（重新）生成本周周报，同窗口幂等复用同一行。"""
    enforce_rate_limit(request, "admin.weekly")
    from services.research import create_weekly

    r = create_weekly(db)
    job = enqueue_job(
        db,
        "weekly_report_generate",
        {"report_id": r.id},
        idempotency_key=f"weekly-report:{r.id}",
    )
    return { "id": r.id, "title": r.title, "status": r.status,
             "job_id": job.id, "status_url": f"/api/admin/jobs/{job.id}" }


@router.post("/digest")
def digest_now(request: Request, db: Session = Depends(get_db)):
    """立即（重新）生成今日精选，幂等。"""
    enforce_rate_limit(request, "admin.digest")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    job = enqueue_job(
        db,
        "daily_digest_generate",
        {},
        idempotency_key=f"daily-digest:{day}",
    )
    return {"id": job.id, "title": "今日精选生成任务", "total": 0,
            "job_id": job.id, "status_url": f"/api/admin/jobs/{job.id}"}


@router.get("/pipeline")
def pipeline_status(db: Session = Depends(get_db)):
    """流水线全景一次取齐：定时监控 + 手动采集 + 入库/精选节奏 + 信源健康 + 日报新鲜度。

    专为「系统到底在不在干活」的可视化服务——前端侧栏脉搏与流水线页仪表盘都用它。
    时间均为 UTC naive（与 crawled_at 同基准），前端补 Z 转本地。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = now - timedelta(hours=24)

    def _cnt(*conds) -> int:
        return int(db.scalar(select(func.count()).select_from(schema.Article).where(*conds)) or 0)

    last_crawled = db.scalar(select(func.max(schema.Article.crawled_at)))
    articles = {
        "total": _cnt(),
        "added_24h": _cnt(schema.Article.crawled_at >= day_ago),
        "curated_24h": _cnt(schema.Article.crawled_at >= day_ago, schema.Article.curated.is_(True)),
        "noise_24h": _cnt(schema.Article.crawled_at >= day_ago, schema.Article.noise_reason.isnot(None)),
        "last_crawled_at": last_crawled.isoformat() if last_crawled else None,
        "unscored_backlog": count_unscored_backlog(db),
    }

    srcs = db.scalars(select(schema.Source)).all()
    ok = err = never = 0
    errors: list[dict] = []
    blocked: list[dict] = []
    for s in srcs:
        builtin = s.name in BUILTIN_SOURCE_NAMES
        if not builtin and s.status != "已采纳":
            continue
        # 内置采集器由代码始终抓取（DB 行只是登记健康状态），不进 blocked
        if not builtin and not source_is_crawlable(s):
            # 已采纳却不会被抓取的两类：缺 URL 的 RSS/公众号（配置问题，须醒目）、
            # 无解析器的网站类（已知限制）
            if s.type in ("RSS", "公众号"):
                blocked.append({"name": s.name, "reason": "未填写 URL，不参与抓取"})
            else:
                blocked.append({"name": s.name, "reason": "网站类暂无解析器，不自动抓取"})
            continue
        if s.last_status == "ok":
            ok += 1
        elif s.last_status == "error":
            err += 1
            errors.append({
                "name": s.name,
                "error": (s.last_error or "")[:200],
                "at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
            })
        else:
            never += 1

    latest_daily = db.scalar(
        select(schema.Report).where(schema.Report.type == "daily")
        .order_by(schema.Report.id.desc()).limit(1)
    )
    digest = {
        "title": latest_daily.title,
        "total": (latest_daily.content_json or {}).get("total", 0),
        "created_at": latest_daily.created_at.isoformat() if latest_daily.created_at else None,
    } if latest_daily else None

    return {
        "server_time": now.isoformat(),
        "monitor": monitor_status(),
        "manual_crawl": crawl_status(db),
        "articles": articles,
        "sources": {"ok": ok, "error": err, "never": never,
                    "errors": errors, "blocked": blocked},
        "digest": digest,
    }


@router.get("/sources/health")
def sources_health(db: Session = Depends(get_db)):
    """信源健康 + 产出价值。

    只看「能不能抓到」不足以决定一个信源该不该留 —— 实测有信源连续抓了 155 条、
    抓取状态一直是 ok，却 80% 被判噪音、从未产出过一条精选，纯粹在消耗采集预算
    和模型调用。因此把噪音率与精选/电力轴产出一并暴露出来，让「该砍谁」有据可依。
    """
    stats = {
        row.source_id: row
        for row in db.execute(
            select(
                schema.Article.source_id,
                func.count().label("n"),
                func.sum(case((schema.Article.noise_reason.isnot(None), 1), else_=0)).label("noise_n"),
                func.sum(case((schema.Article.curated, 1), else_=0)).label("curated_n"),
                func.sum(case((schema.Article.axis.in_(("交叉", "行业")), 1), else_=0)).label("power_n"),
            ).group_by(schema.Article.source_id)
        ).all()
    }
    rows = db.scalars(select(schema.Source)).all()
    payload = []
    for s in rows:
        stat = stats.get(s.id)
        total = int(stat.n) if stat else 0
        noise_n = int(stat.noise_n or 0) if stat else 0
        payload.append({
            "id": s.id, "name": s.name, "type": s.type, "status": s.status, "tier": s.tier,
            "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
            "last_status": s.last_status, "last_error": s.last_error,
            "article_count": total,
            "noise_pct": round(100.0 * noise_n / total) if total else 0,
            "curated_count": int(stat.curated_n or 0) if stat else 0,
            "power_count": int(stat.power_n or 0) if stat else 0,
        })
    return payload


@router.get("/axis")
def axis_monitor(days: int = 7, db: Session = Depends(get_db)):
    """双轴监控：AI 轴 / 电力轴的供给分布，用于回答「行业侧内容到底有没有」。

    这是本产品最需要盯的一张表 —— 「四不像」的本质就是行业侧供给长期为零却看不见。
    三个切面：
      by_axis   总体分布 + 各轴的平均分与精选数（全量，不受 days 影响）
      by_source 每个信源实际产出哪一轴（全量，不受 days 影响）
      trend     逐日分布（判断某轴是不是断供了；**仅此项**受 days 窗口约束）

    前两项刻意用全量：「这个源该留该砍」「行业侧结构性缺不缺供给」问的是长期
    结构，短窗口样本不足会让判断随机跳动。days 只用来控制趋势线的长度。
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, min(days, 90)))
    scored = schema.Article.noise_reason.is_(None)

    by_axis = [
        {
            "axis": row.axis or "弱",
            "count": row.n,
            "curated": row.cur or 0,
            "avg_cross": round(float(row.avg_cross or 0)),
            "avg_quality": round(float(row.avg_quality or 0)),
        }
        for row in db.execute(
            select(
                schema.Article.axis,
                func.count().label("n"),
                func.sum(func.cast(schema.Article.curated, Integer)).label("cur"),
                func.avg(schema.Article.cross_score).label("avg_cross"),
                func.avg(schema.Article.relevance_score).label("avg_quality"),
            ).where(scored).group_by(schema.Article.axis)
        ).all()
    ]

    by_source = [
        {
            "source": row.name or "未知",
            "tier": row.tier or "T2",
            "count": row.n,
            "cross": row.cross_n or 0,
            "ai": row.ai_n or 0,
            "power": row.power_n or 0,
            "avg_cross": round(float(row.avg_cross or 0)),
        }
        for row in db.execute(
            select(
                schema.Source.name,
                schema.Source.tier,
                func.count().label("n"),
                func.sum(_axis_flag("交叉")).label("cross_n"),
                func.sum(_axis_flag("AI")).label("ai_n"),
                func.sum(_axis_flag("行业")).label("power_n"),
                func.avg(schema.Article.cross_score).label("avg_cross"),
            )
            .join(schema.Source, schema.Source.id == schema.Article.source_id)
            .where(scored)
            .group_by(schema.Source.name, schema.Source.tier)
            .order_by(func.count().desc())
            .limit(40)
        ).all()
    ]

    day = func.date(schema.Article.crawled_at)
    trend = [
        {
            "day": str(row.day),
            "cross": row.cross_n or 0,
            "ai": row.ai_n or 0,
            "power": row.power_n or 0,
            "weak": row.weak_n or 0,
        }
        for row in db.execute(
            select(
                day.label("day"),
                func.sum(_axis_flag("交叉")).label("cross_n"),
                func.sum(_axis_flag("AI")).label("ai_n"),
                func.sum(_axis_flag("行业")).label("power_n"),
                func.sum(_axis_flag("弱")).label("weak_n"),
            ).where(scored, schema.Article.crawled_at >= cutoff).group_by(day).order_by(day)
        ).all()
    ]

    total = sum(item["count"] for item in by_axis) or 1
    power_supply = sum(item["count"] for item in by_axis if item["axis"] in ("交叉", "行业"))
    return {
        "by_axis": sorted(by_axis, key=lambda item: -item["count"]),
        "by_source": by_source,
        "trend": trend,
        # 行业侧供给占比：这个数长期低于 20% 就说明又退回「纯 AI 资讯站」了
        "power_supply_ratio": round(100.0 * power_supply / total, 1),
        # 只描述 trend 的跨度；by_axis / by_source / power_supply_ratio 均为全量
        "trend_window_days": days,
    }
