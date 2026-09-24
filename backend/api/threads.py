from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dto import ResearchThreadCreate, ResearchThreadOut, ResearchThreadUpdate
from core.auth import require_admin, require_workspace
from models import schema
from models.database import get_db

router = APIRouter(prefix="/threads", tags=["threads"])


def get_thread(db: Session, thread_id: int) -> schema.ResearchThread:
    thread = db.get(schema.ResearchThread, thread_id)
    if thread is None:
        raise HTTPException(404, "research thread not found")
    return thread


def name_key_for(db: Session, name: str, exclude_id: int | None = None) -> str:
    name_key = schema.normalize_thread_name(name)
    existing = db.scalar(select(schema.ResearchThread).where(schema.ResearchThread.name_key == name_key))
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(409, "research thread name already exists")
    return name_key


@router.get("", response_model=list[ResearchThreadOut])
def list_threads(
    include_paused: bool = Query(False),
    role: str = Depends(require_workspace),
    db: Session = Depends(get_db),
):
    if include_paused and role != "admin":
        raise HTTPException(403, "Administrator access required")
    query = select(schema.ResearchThread).order_by(schema.ResearchThread.id)
    if not include_paused:
        query = query.where(schema.ResearchThread.status == "active")
    return list(db.scalars(query))


@router.get("/summary")
def thread_summary(db: Session = Depends(get_db)):
    threads = list(db.scalars(
        select(schema.ResearchThread).where(schema.ResearchThread.status == "active").order_by(schema.ResearchThread.id)
    ))
    counts = dict(db.execute(
        select(schema.Article.primary_thread_id, func.count())
        .where(schema.Article.scored.is_(True), schema.Article.primary_thread_id.isnot(None))
        .group_by(schema.Article.primary_thread_id)
    ).all())
    horizon = int(db.scalar(
        select(func.count()).select_from(schema.Article).where(
            schema.Article.scored.is_(True), schema.Article.primary_thread_id.is_(None)
        )
    ) or 0)
    return [
        *[{"id": thread.id, "name": thread.name, "count": counts.get(thread.id, 0)} for thread in threads],
        {"id": None, "name": "视野", "count": horizon},
    ]


@router.post("", response_model=ResearchThreadOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_thread(payload: ResearchThreadCreate, db: Session = Depends(get_db)):
    thread = schema.ResearchThread(**payload.model_dump(), name_key=name_key_for(db, payload.name))
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.patch("/{thread_id}", response_model=ResearchThreadOut, dependencies=[Depends(require_admin)])
def update_thread(thread_id: int, payload: ResearchThreadUpdate, db: Session = Depends(get_db)):
    thread = get_thread(db, thread_id)
    values = payload.model_dump(exclude_unset=True)
    if "name" in values:
        thread.name_key = name_key_for(db, values["name"], thread.id)
    for key, value in values.items():
        setattr(thread, key, value)
    db.commit()
    db.refresh(thread)
    return thread


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = get_thread(db, thread_id)
    referenced = db.scalar(select(schema.Article.id).where(schema.Article.primary_thread_id == thread.id).limit(1))
    if referenced is not None:
        raise HTTPException(409, "research thread has historical article references")
    db.delete(thread)
    db.commit()
