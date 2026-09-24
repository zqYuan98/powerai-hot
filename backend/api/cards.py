"""知识卡片：列表/搜索/笔记/重试。"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.auth import require_admin
from core.rate_limit import enforce_rate_limit
from core.sqlutil import escape_like
from models import schema
from models.database import get_db
from jobs.queue import enqueue_job
from services.cards import generate_card  # compatibility import for existing extensions

router = APIRouter(prefix="/cards", tags=["cards"])


def _card_out(c: schema.KnowledgeCard, a: schema.Article | None) -> dict:
    return {
        "id": c.id, "article_id": c.article_id, "category": c.category,
        "problem": c.problem, "method": c.method, "conclusion": c.conclusion,
        "power_relevance": c.power_relevance, "note": c.note, "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "article": {
            "title": a.title, "url": a.url, "channel": a.channel, "kind": a.kind,
            "title_zh": (a.meta or {}).get("title_zh"),
        } if a else None,
    }


@router.get("")
def list_cards(
    category: str | None = Query(None),
    q: str | None = Query(None, description="搜索：标题/问题/方法/结论/笔记"),
    db: Session = Depends(get_db),
):
    stmt = (
        select(schema.KnowledgeCard, schema.Article)
        .join(schema.Article, schema.KnowledgeCard.article_id == schema.Article.id)
        .join(schema.Favorite, schema.Favorite.article_id == schema.KnowledgeCard.article_id)
        .order_by(schema.KnowledgeCard.id.desc())
    )
    if category:
        stmt = stmt.where(schema.KnowledgeCard.category == category)
    if q:
        like = f"%{escape_like(q)}%"
        stmt = stmt.where(or_(
            schema.Article.title.ilike(like, escape="\\"),
            schema.KnowledgeCard.problem.ilike(like, escape="\\"),
            schema.KnowledgeCard.method.ilike(like, escape="\\"),
            schema.KnowledgeCard.conclusion.ilike(like, escape="\\"),
            schema.KnowledgeCard.note.ilike(like, escape="\\"),
        ))
    return [_card_out(c, a) for c, a in db.execute(stmt).all()]


class CardPatch(BaseModel):
    note: str | None = None
    category: str | None = None


@router.patch("/{card_id}")
def patch_card(card_id: int, payload: CardPatch, db: Session = Depends(get_db)):
    card = db.get(schema.KnowledgeCard, card_id)
    if not card:
        raise HTTPException(404, "card not found")
    if payload.note is not None:
        card.note = payload.note
    if payload.category is not None:
        card.category = payload.category
    db.commit()
    return _card_out(card, db.get(schema.Article, card.article_id))


@router.post("/{card_id}/retry", dependencies=[Depends(require_admin)])
def retry_card(
    card_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "cards.retry")
    card = db.get(schema.KnowledgeCard, card_id)
    if not card:
        raise HTTPException(404, "card not found")
    card.status = "生成中"
    db.commit()
    key = f"card-retry:{card_id}:{datetime.now(UTC).timestamp()}"
    job = enqueue_job(db, "card_retry", {"card_id": card_id}, idempotency_key=key)
    return {"id": card_id, "status": "生成中", "job_id": job.id,
            "status_url": f"/api/admin/jobs/{job.id}"}
