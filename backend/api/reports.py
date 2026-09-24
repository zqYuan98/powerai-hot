"""日报/周报/研报的列表、详情、发起与重试。daily 详情把 article_ids 水合成完整文章。"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dto import ArticleOut
from core.auth import require_admin
from core.rate_limit import enforce_rate_limit
from models import schema
from models.database import get_db
from jobs.queue import enqueue_job
from services.research import create_topic

router = APIRouter(prefix="/reports", tags=["reports"])


def _summary(r: schema.Report) -> dict:
    return {
        "id": r.id, "type": r.type, "title": r.title, "status": r.status,
        "total": (r.content_json or {}).get("total"),
        "period_start": r.period_start.isoformat() if r.period_start else None,
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("")
def list_reports(type: str | None = Query(None), db: Session = Depends(get_db)):
    stmt = select(schema.Report).order_by(schema.Report.id.desc())
    if type:
        stmt = stmt.where(schema.Report.type == type)
    return [_summary(r) for r in db.scalars(stmt).all()]


class TopicRequest(BaseModel):
    topic: str


@router.post("/topic", dependencies=[Depends(require_admin)])
def create_topic_report(
    payload: TopicRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """发起主题研报：立即返回，后台检索选材并生成，前端轮询状态。"""
    enforce_rate_limit(request, "reports.topic")
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(400, "主题不能为空")
    report = create_topic(db, topic)
    job = enqueue_job(db, "topic_report_generate", {"report_id": report.id}, idempotency_key=f"topic-report:{report.id}")
    return {"id": report.id, "title": report.title, "status": report.status,
            "job_id": job.id, "status_url": f"/api/admin/jobs/{job.id}"}


@router.post("/{report_id}/retry", dependencies=[Depends(require_admin)])
def retry_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "reports.retry")
    r = db.get(schema.Report, report_id)
    if not r:
        raise HTTPException(404, "report not found")
    if r.type == "daily":
        raise HTTPException(400, "日报请用 POST /api/admin/digest 重新生成")
    r.status = "生成中"
    db.commit()
    job_type = "weekly_report_generate" if r.type == "weekly" else "topic_report_generate"
    key = f"report-retry:{report_id}:{datetime.now(UTC).timestamp()}"
    job = enqueue_job(db, job_type, {"report_id": report_id}, idempotency_key=key)
    return {"id": report_id, "status": "生成中", "job_id": job.id,
            "status_url": f"/api/admin/jobs/{job.id}"}


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    r = db.get(schema.Report, report_id)
    if not r:
        raise HTTPException(404, "report not found")
    sections = []
    for sec in (r.content_json or {}).get("sections", []):
        arts = db.scalars(
            select(schema.Article).where(schema.Article.id.in_(sec["article_ids"]))
        ).all()
        by_id = {a.id: a for a in arts}
        ordered = [by_id[i] for i in sec["article_ids"] if i in by_id]
        sections.append({
            "name": sec["name"],
            "articles": [ArticleOut.model_validate(a).model_dump() for a in ordered],
        })
    return {**_summary(r), "content_md": r.content_md, "sections": sections}
