"""知识库：访客看已通过的知识卡片；收录、隐藏、重试与正文只对管理员开放。"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Admin
from app.collectors.urlguard import UnsafeUrl, validate_public_url
from app.db import get_session
from app.models import Article, Item
from app.models.enums import DOMAIN_LABELS, KTYPE_LABELS, ArticleStatus, KnowledgeDomain, KnowledgeType
from app.pipeline.knowledge import BODY_LIMIT, FEATURED_SCORE, article_key
from app.schemas.dto import (
    FacetCount,
    KnowledgeCard,
    KnowledgeDetail,
    KnowledgeDims,
    KnowledgeFacets,
    KnowledgePage,
    KnowledgePatch,
    KnowledgeSubmit,
    KnowledgeSubmitAck,
    Ok,
)
from app.worker import queue

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
admin_router = APIRouter(prefix="/knowledge", tags=["knowledge"])
Session = Annotated[AsyncSession, Depends(get_session)]
SHOWN = ArticleStatus.ANALYZED.value
RELATED_DISTANCE = 0.40       # 知识 ↔ 知识
ITEM_RELATED_DISTANCE = 0.45  # 商机/资讯 ↔ 知识（文本风格不同，放宽一点）
SEARCH_EXPR = (func.coalesce(Article.title_zh, "") + " " + Article.title + " " + func.coalesce(Article.summary, "")
               + " " + func.array_to_string(Article.key_points, " ") + " " + func.array_to_string(Article.tags, " "))
SORTS: dict[str, tuple[Any, ...]] = {
    "score": (Article.score.desc().nulls_last(), Article.id.desc()),
    "recent": (Article.created_at.desc(), Article.id.desc()),
}


def to_knowledge(a: Article, *, private: bool = False) -> KnowledgeCard:
    return KnowledgeCard(
        id=a.id, title=a.title_zh or a.title, original_title=a.title, url=a.url,
        account=a.account or (a.source.name if a.source else None), published_at=a.published_at,
        created_at=a.created_at, domain=KnowledgeDomain(a.domain), ktype=KnowledgeType(a.ktype), tags=a.tags or [],
        summary=a.summary, key_points=a.key_points or [], scenarios=a.scenarios, solution_use=a.solution_use,
        standards=a.standards or [], score=a.score, featured=(a.score or 0) >= FEATURED_SCORE,
        status=a.status,  # type: ignore[arg-type]
        status_reason=a.status_reason if private else None,
    )


def visible_conds(domain: KnowledgeDomain | None, ktype: KnowledgeType | None, q: str | None) -> list[Any]:
    conds: list[Any] = []
    if domain:
        conds.append(Article.domain == domain)
    if ktype:
        conds.append(Article.ktype == ktype)
    if q:
        conds.append(SEARCH_EXPR.ilike(f"%{q.strip()}%"))
    return conds


@router.get("", response_model=KnowledgePage)
async def list_knowledge(
    session: Session,
    admin: Admin,
    domain: KnowledgeDomain | None = None,
    ktype: KnowledgeType | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    featured: bool = False,
    sort: Literal["score", "recent"] = "score",
    status: ArticleStatus | None = None,  # 只对管理员有效：查看待处理、失败、未通过的
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> KnowledgePage:
    conds = visible_conds(domain, ktype, q)
    conds.append(Article.status == (status if status and admin else SHOWN))
    if featured:
        conds.append(Article.score >= FEATURED_SCORE)
    total = await session.scalar(select(func.count()).select_from(Article).where(*conds)) or 0
    rows = await session.scalars(select(Article).where(*conds).order_by(*SORTS[sort]).offset(offset).limit(limit))
    return KnowledgePage(items=[to_knowledge(a, private=admin) for a in rows], total=total)


@router.get("/facets", response_model=KnowledgeFacets)
async def knowledge_facets(session: Session, admin: Admin) -> KnowledgeFacets:
    async def counts(col: Any) -> dict[str, int]:
        rows = await session.execute(select(col, func.count()).where(Article.status == SHOWN).group_by(col))
        return {k: n for k, n in rows.all()}

    domains, types = await counts(Article.domain), await counts(Article.ktype)
    status: dict[str, int] = {}
    if admin:
        status = {k: n for k, n in (await session.execute(
            select(Article.status, func.count()).group_by(Article.status))).all()}
    return KnowledgeFacets(
        total=sum(domains.values()),
        domains=[FacetCount(key=d, label=DOMAIN_LABELS[d], count=domains.get(d, 0)) for d in KnowledgeDomain],
        types=[FacetCount(key=t, label=KTYPE_LABELS[t], count=types.get(t, 0)) for t in KnowledgeType],
        status=status,
    )


@router.get("/related", response_model=list[KnowledgeCard])
async def related_to_item(session: Session, item_id: int,
                          limit: Annotated[int, Query(ge=1, le=10)] = 4) -> list[KnowledgeCard]:
    """与一条资讯/商机语义相近的知识（没配置 Embedding 或没有足够接近的就返回空）。"""
    vector = await session.scalar(select(Item.embedding).where(Item.id == item_id))
    if vector is None:
        return []
    distance = Article.embedding.cosine_distance(vector)
    rows = await session.scalars(
        select(Article).where(Article.status == SHOWN, Article.embedding.is_not(None),
                              distance < ITEM_RELATED_DISTANCE).order_by(distance).limit(limit)
    )
    return [to_knowledge(a) for a in rows]


async def _related(session: AsyncSession, a: Article) -> list[KnowledgeCard]:
    base = select(Article).where(Article.id != a.id, Article.status == SHOWN)
    if a.embedding is not None:
        distance = Article.embedding.cosine_distance(a.embedding)
        stmt = base.where(Article.embedding.is_not(None), distance < RELATED_DISTANCE).order_by(distance)
    else:  # 没有向量时退回同专业、同类型里分数最高的
        stmt = base.where(Article.domain == a.domain, Article.ktype == a.ktype).order_by(*SORTS["score"])
    return [to_knowledge(r) for r in await session.scalars(stmt.limit(5))]


@router.get("/{article_id}", response_model=KnowledgeDetail)
async def get_knowledge(session: Session, admin: Admin, article_id: int) -> KnowledgeDetail:
    a = await session.get(Article, article_id)
    if a is None or (not admin and a.status != SHOWN):
        raise HTTPException(404, "文章不存在")
    return KnowledgeDetail(
        **to_knowledge(a, private=admin).model_dump(),
        dims=KnowledgeDims(depth=a.d_depth, practical=a.d_practical, accuracy=a.d_accuracy, originality=a.d_original),
        related=await _related(session, a),
        content_text=a.content_text if admin else None,
        note=a.note if admin else None,
        duplicate_of=a.duplicate_of if admin else None,
    )


# ---------- 管理 ----------

async def _enqueue(session: AsyncSession, article_id: int) -> None:
    await queue.enqueue(session, "article_process", {"article_id": article_id}, priority=3,
                        dedupe_key=f"article:{article_id}")


@admin_router.post("", response_model=KnowledgeSubmitAck, status_code=201)
async def submit_knowledge(session: Session, body: KnowledgeSubmit) -> KnowledgeSubmitAck:
    """粘贴链接收录；抓不到正文（公众号风控、纯图片）时可以连同正文一起提交。"""
    try:
        await validate_public_url(body.url)
    except UnsafeUrl as exc:
        raise HTTPException(422, f"链接不可用：{exc}") from exc
    content = body.content[:BODY_LIMIT] if body.content else None
    title = body.title or (content.splitlines()[0][:80] if content else None)
    key = article_key(body.url)
    existing = (await session.scalars(select(Article).where(Article.url_hash == key))).first()
    if existing is not None:
        # 之前抓取失败的，补上正文后重新处理；其余情况原样返回
        if content and existing.status in (ArticleStatus.FAILED, ArticleStatus.NEW):
            existing.content_text, existing.title = content, title or existing.title
            existing.status, existing.status_reason, existing.attempts = ArticleStatus.NEW.value, None, 0
            await _enqueue(session, existing.id)
        if body.note:
            existing.note = body.note
        await session.commit()
        return KnowledgeSubmitAck(id=existing.id, existed=True, status=existing.status)
    a = Article(url=body.url, url_hash=key, title=title or body.url, content_text=content, note=body.note)
    session.add(a)
    await session.flush()
    await _enqueue(session, a.id)
    await session.commit()
    return KnowledgeSubmitAck(id=a.id, existed=False, status=a.status)


@admin_router.patch("/{article_id}", response_model=KnowledgeCard)
async def patch_knowledge(session: Session, article_id: int, body: KnowledgePatch) -> KnowledgeCard:
    a = await session.get(Article, article_id)
    if a is None:
        raise HTTPException(404, "文章不存在")
    fields = body.model_dump(exclude_unset=True)
    if "note" in fields:
        a.note = body.note or None
    if body.domain:
        a.domain = body.domain.value
    if body.ktype:
        a.ktype = body.ktype.value
    if body.hidden is True and a.status == ArticleStatus.ANALYZED:
        a.status, a.status_reason = ArticleStatus.HIDDEN.value, "管理员隐藏"
    elif body.hidden is False and a.status in (ArticleStatus.HIDDEN, ArticleStatus.REJECTED, ArticleStatus.DUPLICATE):
        a.status, a.status_reason = ArticleStatus.ANALYZED.value, None  # 人工确认展示，推翻模型判断
    await session.commit()
    return to_knowledge(a, private=True)


@admin_router.post("/{article_id}/retry", response_model=Ok)
async def retry_knowledge(session: Session, article_id: int) -> Ok:
    a = await session.get(Article, article_id)
    if a is None:
        raise HTTPException(404, "文章不存在")
    a.status, a.status_reason, a.attempts, a.duplicate_of = ArticleStatus.NEW.value, None, 0, None
    await _enqueue(session, a.id)
    await session.commit()
    return Ok(detail="已加入队列")


@admin_router.delete("/{article_id}", response_model=Ok)
async def delete_knowledge(session: Session, article_id: int) -> Ok:
    a = await session.get(Article, article_id)
    if a is None:
        raise HTTPException(404, "文章不存在")
    await session.delete(a)
    await session.commit()
    return Ok()
