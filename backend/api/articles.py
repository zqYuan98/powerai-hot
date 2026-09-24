"""文章列表、详情、搜索、事件簇展开。"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from api.dto import ArticleDetail, ArticleFreshness, ArticleOut, ArticlePage, ArticleTimeline
from core.constants import CHANNELS
from models.database import get_db
from models import schema
from services.article_feed import (
    FeedQuery,
    count_channels,
    fetch_page,
    get_freshness,
    get_cross_picks,
    get_hotspots,
    get_timeline,
)
from services.clustering import TIER_RANK

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=ArticlePage)
def list_articles(
    channel: str | None = Query(None, description="频道：行业动态/国网规划/招标公告/AI洞察/政策法规"),
    thread_id: int | None = Query(None, gt=0, description="研究主线 ID"),
    q: str | None = Query(None, description="关键词搜索（标题/摘要）"),
    kind: str | None = Query(None, description="内容类型：资讯/论文/案例"),
    curated: bool | None = Query(None, description="兼容旧调用；true 等价 view=curated"),
    min_score: int = Query(0, description="最低相关度分"),
    include_all: bool = Query(False, description="含被折叠的簇内成员"),
    view: Literal["curated", "all", "noise"] = Query("curated"),
    window: Literal["24h", "7d", "all"] = Query("all"),
    tag: str | None = Query(None),
    axis: Literal["交叉", "AI", "行业", "弱"] | None = Query(None, description="双轴分类筛选"),
    sort: Literal["score", "latest"] | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if curated is True:
        view = "curated"
    effective_sort = sort or ("score" if view == "curated" else "latest")
    query = FeedQuery(
        channel=channel, thread_id=thread_id, q=q, kind=kind, min_score=min_score,
        include_all=include_all, view=view, window=window, tag=tag, sort=effective_sort,
        axis=axis,
    )
    try:
        return fetch_page(db, query, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/channels")
def channel_counts(
    q: str | None = Query(None), kind: str | None = Query(None),
    min_score: int = Query(0), view: Literal["curated", "all", "noise"] = Query("curated"),
    window: Literal["24h", "7d", "all"] = Query("all"), tag: str | None = Query(None),
    sort: Literal["score", "latest"] | None = Query(None),
    channel: str | None = Query(None, include_in_schema=False),
    db: Session = Depends(get_db),
):
    """Tab counts for the feed header."""
    effective_sort = sort or ("score" if view == "curated" else "latest")
    counts = count_channels(db, FeedQuery(q=q, kind=kind, min_score=min_score, view=view,
                                           window=window, tag=tag, sort=effective_sort))
    return [{"name": name, "count": counts.get(name, 0)} for name in CHANNELS]


@router.get("/freshness", response_model=ArticleFreshness)
def freshness(db: Session = Depends(get_db)):
    return get_freshness(db)


@router.get("/timeline", response_model=ArticleTimeline)
def timeline(hours: int = Query(48, ge=6, le=168), db: Session = Depends(get_db)):
    """入库时间线：近 N 小时逐小时入库量，供前端「更新时间线」与停采预警。"""
    return get_timeline(db, hours)


@router.get("/hotspots", response_model=list[ArticleOut])
def hotspots(limit: int = Query(5, ge=1, le=10), db: Session = Depends(get_db)):
    return get_hotspots(db, limit)


@router.get("/cross-picks", response_model=list[ArticleOut])
def cross_picks(limit: int = Query(4, ge=1, le=12), db: Session = Depends(get_db)):
    """交叉精选：AI 技术轴与电力业务轴同时命中的情报，按交叉分排序。"""
    return get_cross_picks(db, limit)


@router.get("/{article_id}/cluster", response_model=list[ArticleOut])
def get_cluster(article_id: int, db: Session = Depends(get_db)):
    """展开事件簇全部条目（主条在前）。"""
    art = db.get(schema.Article, article_id)
    if not art:
        raise HTTPException(404, "article not found")
    if not art.cluster_id:
        return [art]
    members = db.scalars(
        select(schema.Article).where(schema.Article.cluster_id == art.cluster_id)
    ).all()
    members.sort(key=lambda a: (TIER_RANK.get(a.tier, 2), -(a.relevance_score or 0), a.id))
    return members


@router.get("/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int, db: Session = Depends(get_db)):
    art = db.get(schema.Article, article_id)
    if not art:
        raise HTTPException(404, "article not found")
    # 原子自增：避免并发访问同一详情页时读-改-写丢更新
    db.execute(
        update(schema.Article)
        .where(schema.Article.id == article_id)
        .values(view_count=schema.Article.view_count + 1)
    )
    db.commit()
    db.refresh(art)
    return art
