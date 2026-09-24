"""收藏：加入/移出个人知识库。收藏即异步生成知识卡片。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import schema
from models.database import get_db
from jobs.queue import enqueue_job
from services.cards import generate_card  # compatibility import for existing extensions

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _insert_for_article_once(db: Session, model, article_id: int) -> int | None:
    """Insert a unique article row and return its id only to the creator."""
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(model).values(article_id=article_id)
    elif dialect == "postgresql":
        statement = postgresql_insert(model).values(article_id=article_id)
    else:
        try:
            with db.begin_nested():
                row = model(article_id=article_id)
                db.add(row)
                db.flush()
                return row.id
        except IntegrityError:
            existing_id = db.scalar(
                select(model.id).where(model.article_id == article_id)
            )
            if existing_id is None:
                raise
            return None

    statement = statement.on_conflict_do_nothing(
        index_elements=[model.article_id]
    ).returning(model.id)
    return db.scalar(statement)


@router.get("")
def list_favorite_ids(db: Session = Depends(get_db)):
    """已收藏文章 id 列表（前端用来渲染星标状态）。"""
    return [f.article_id for f in db.scalars(select(schema.Favorite)).all()]


@router.post("/{article_id}")
def add_favorite(article_id: int, db: Session = Depends(get_db)):
    if not db.get(schema.Article, article_id):
        raise HTTPException(404, "article not found")
    # End the existence-check read transaction before either concurrent writer
    # attempts an upsert (important for SQLite WAL snapshot upgrades).
    db.commit()

    _insert_for_article_once(db, schema.Favorite, article_id)
    created_card_id = _insert_for_article_once(db, schema.KnowledgeCard, article_id)
    db.commit()

    card_id = created_card_id or db.scalar(
        select(schema.KnowledgeCard.id).where(
            schema.KnowledgeCard.article_id == article_id
        )
    )
    if created_card_id is not None:
        job = enqueue_job(
            db,
            "favorite_card_generate",
            {"card_id": created_card_id},
            idempotency_key=f"favorite-card:{created_card_id}",
        )
    else:
        job = None
    return {"favorited": True, "article_id": article_id, "card_id": card_id,
            "job_id": job.id if job else None,
            "status_url": f"/api/admin/jobs/{job.id}" if job else None}


@router.delete("/{article_id}")
def remove_favorite(article_id: int, db: Session = Depends(get_db)):
    """Remove the favorite while retaining any generated card and its notes."""
    fav = db.scalar(select(schema.Favorite).where(schema.Favorite.article_id == article_id))
    if fav:
        db.delete(fav)
    db.commit()
    return {"favorited": False, "article_id": article_id}
