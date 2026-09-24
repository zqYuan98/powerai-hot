"""信源提报与管理。"""
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dto import SourceCreate, SourceOut, SourceSubmissionCreate
from core.auth import require_admin, require_workspace
from core.urlguard import validate_feed_url
from models.database import get_db
from models import schema
from services.ingest import BUILTIN_SOURCE_NAMES, source_is_crawlable

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_out(src: schema.Source, stats: dict | None = None) -> SourceOut:
    out = SourceOut.model_validate(src)
    out.builtin = src.name in BUILTIN_SOURCE_NAMES
    out.crawlable = source_is_crawlable(src)
    row = (stats or {}).get(src.id)
    if row:
        total = int(row.n or 0)
        out.article_count = total
        out.noise_pct = round(100.0 * int(row.noise_n or 0) / total) if total else 0
        out.curated_count = int(row.curated_n or 0)
        out.power_count = int(row.power_n or 0)
    return out


def _source_value_stats(db: Session) -> dict:
    """每个信源的产出价值，一次聚合查完（避免逐行 N+1）。

    只看「抓取状态 ok」决定不了一个信源该不该留：实测有信源连抓 155 条、
    状态一直 ok，却 80% 判噪音、零精选，纯耗采集预算与模型调用。
    """
    return {
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


@router.get("", response_model=list[SourceOut], dependencies=[Depends(require_admin)])
def list_sources(mine: bool = False, db: Session = Depends(get_db)):
    stmt = select(schema.Source)
    if mine:
        stmt = stmt.where(schema.Source.submitted_by == "me")
    rows = db.scalars(stmt.order_by(schema.Source.created_at.desc())).all()
    stats = _source_value_stats(db)
    return [_to_out(s, stats) for s in rows]


def _normalize_name(name: str) -> str:
    """Normalize user-entered names for duplicate detection."""
    return schema.normalize_source_name(name)


def _normalize_url(url: str | None) -> str | None:
    """Normalize URL casing/whitespace while retaining meaningful path/query."""
    return schema.normalize_source_url(url)


def _is_source_key_conflict(exc: IntegrityError) -> bool:
    """Identify only the source normalized-key uniqueness constraints."""
    message = str(getattr(exc, "orig", exc)).casefold()
    return (
        "uq_sources_name_key" in message
        or "uq_sources_url_key" in message
        or "sources.name_key" in message
        or "sources.url_key" in message
    )


@router.get("/submissions", response_model=list[SourceOut],
            dependencies=[Depends(require_workspace)])
def list_source_submissions(db: Session = Depends(get_db)):
    """List employee submissions only, newest first, for workspace users/admins."""
    rows = db.scalars(
        select(schema.Source)
        .where(schema.Source.submitted_by == "workspace")
        .order_by(schema.Source.created_at.desc(), schema.Source.id.desc())
    ).all()
    return [_to_out(source) for source in rows]


@router.post("/submissions", response_model=SourceOut, status_code=201,
             dependencies=[Depends(require_workspace)])
def create_source_submission(
    payload: SourceSubmissionCreate,
    db: Session = Depends(get_db),
):
    """Create a pending employee submission; activation is never accepted here."""
    try:
        # All submitted URLs can eventually be fetched by the collector.  Keep
        # the same SSRF/file/loopback protections for website and feed types.
        validate_feed_url(payload.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    normalized_name = _normalize_name(payload.name)
    normalized_url = _normalize_url(payload.url)
    for existing in db.scalars(select(schema.Source)).all():
        if (
            _normalize_name(existing.name) == normalized_name
            or _normalize_url(existing.url) == normalized_url
        ):
            raise HTTPException(409, "source already exists")

    source = schema.Source(
        name=payload.name,
        url=payload.url,
        name_key=normalized_name,
        url_key=normalized_url,
        type=payload.type,
        reason=payload.reason,
        status="待审核",
        submitted_by="workspace",
    )
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_source_key_conflict(exc):
            raise HTTPException(409, "source already exists") from exc
        raise
    db.refresh(source)
    return _to_out(source)


@router.post("", response_model=SourceOut, status_code=201,
             dependencies=[Depends(require_admin)])
def submit_source(payload: SourceCreate, active: bool = False, db: Session = Depends(get_db)):
    """提交信源。active=true（管理后台添加）直接设为已采纳并纳入监控。"""
    # RSS/公众号 will be fetched by feedparser; preserve the administrator
    # endpoint's existing website compatibility while protecting feed URLs.
    if payload.type in ("RSS", "公众号"):
        try:
            validate_feed_url(payload.url)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    src = schema.Source(
        name=payload.name,
        url=payload.url,
        name_key=_normalize_name(payload.name) or None,
        url_key=_normalize_url(payload.url),
        type=payload.type,
        reason=payload.reason,
        status="已采纳" if active else "待审核",
        # 管理后台直接添加的不算个人提报，否则会混进「我的提报」（?mine=true）列表
        submitted_by="admin" if active else "me",
    )
    db.add(src)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_source_key_conflict(exc):
            raise HTTPException(409, "source already exists") from exc
        raise
    db.refresh(src)
    return _to_out(src)


class OpmlImport(BaseModel):
    opml: str
    active: bool = False  # true=直接采纳纳入采集；false=进待审核


@router.post("/import-opml", dependencies=[Depends(require_admin)])
def import_opml(payload: OpmlImport, db: Session = Depends(get_db)):
    """批量导入 OPML 订阅（RSS 阅读器通用导出格式）。

    解析所有带 xmlUrl 的 outline 节点，逐条走与单个提报相同的 URL 安全校验；
    按 URL / 名称与库中已有信源去重。返回 {imported, skipped, errors}。
    """
    try:
        # OPML 是用户粘贴的纯文本；ET 默认不解析外部实体，无 XXE 风险
        root = ET.fromstring(payload.opml)
    except ET.ParseError as e:
        raise HTTPException(400, f"OPML 解析失败：{e}")

    existing_urls = {
        _normalize_url(u) for (u,) in db.query(schema.Source.url).all() if u
    }
    existing_names = {
        _normalize_name(n) for (n,) in db.query(schema.Source.name).all()
    }
    seen_urls: set[str] = set()
    seen_names: set[str] = set()

    imported, skipped, errors = 0, 0, []
    for node in root.iter("outline"):
        url = (node.get("xmlUrl") or "").strip()
        if not url:
            continue  # 分组节点
        name = (node.get("title") or node.get("text") or url).strip()[:100]
        normalized_name = _normalize_name(name)
        try:
            validate_feed_url(url)
        except ValueError as e:
            errors.append(f"{name}: {e}")
            continue
        normalized_url = _normalize_url(url)
        if (
            normalized_url in existing_urls
            or normalized_url in seen_urls
            or normalized_name in existing_names
            or normalized_name in seen_names
        ):
            skipped += 1
            continue
        db.add(schema.Source(
            name=name, url=url, name_key=normalized_name, url_key=normalized_url,
            type="RSS",
            status="已采纳" if payload.active else "待审核",
            submitted_by="admin", reason="OPML 批量导入",
        ))
        seen_urls.add(normalized_url)
        seen_names.add(normalized_name)
        imported += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_source_key_conflict(exc):
            raise HTTPException(409, "source already exists") from exc
        raise
    return {"imported": imported, "skipped": skipped, "errors": errors}


@router.post("/{source_id}/status", response_model=SourceOut,
             dependencies=[Depends(require_admin)])
def set_status(source_id: int, status: str, db: Session = Depends(get_db)):
    """启用/停用信源：status = 已采纳 | 待审核 | 未通过。已采纳即被监控采集。"""
    if status not in ("已采纳", "待审核", "未通过"):
        raise HTTPException(400, "invalid status")
    src = db.get(schema.Source, source_id)
    if not src:
        raise HTTPException(404, "source not found")
    src.status = status
    db.commit()
    db.refresh(src)
    return _to_out(src)


@router.delete("/{source_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(schema.Source, source_id)
    if not src:
        raise HTTPException(404, "source not found")
    db.delete(src)
    db.commit()
