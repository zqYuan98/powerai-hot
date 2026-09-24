"""订阅管理。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dto import ArticleOut, SubscriptionHit, SubscriptionOut, SubscriptionUpdate
from models.database import get_db
from models import schema

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _get_or_create(db: Session) -> schema.Subscription:
    sub = db.scalar(select(schema.Subscription).where(schema.Subscription.user_id == "me"))
    if not sub:
        sub = schema.Subscription(user_id="me", keywords=[])
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


@router.get("", response_model=SubscriptionOut)
def get_subscription(db: Session = Depends(get_db)):
    return _get_or_create(db)


@router.put("", response_model=SubscriptionOut)
def update_subscription(payload: SubscriptionUpdate, db: Session = Depends(get_db)):
    sub = _get_or_create(db)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(sub, key, value)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/hits", response_model=list[SubscriptionHit])
def subscription_hits(limit: int = Query(3, ge=1, le=20), db: Session = Depends(get_db)):
    """Return a small, bounded set of curated articles matching saved keywords."""
    sub = _get_or_create(db)
    keywords = [value.strip() for value in (sub.keywords or []) if value.strip()]
    if not keywords:
        return []
    candidates = db.scalars(
        select(schema.Article)
        .where(
            schema.Article.scored.is_(True),
            schema.Article.curated.is_(True),
            schema.Article.is_cluster_main.isnot(False),
        )
        .order_by(schema.Article.crawled_at.desc(), schema.Article.id.desc())
        .limit(200)
    ).all()
    hits = []
    for article in candidates:
        title_zh = (article.meta or {}).get("title_zh", "")
        text = f"{title_zh}{article.title or ''}"
        keyword = next((value for value in keywords if value in text), None)
        if keyword is None:
            continue
        hits.append({"article": ArticleOut.model_validate(article), "keyword": keyword})
        if len(hits) >= limit:
            break
    return hits
