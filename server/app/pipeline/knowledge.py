"""知识库处理：抓正文（公众号单独解析）→ 知识卡片精读 → 标准号回原文核验 → 质量门槛 → 转载去重。

与资讯管线分开：不初筛、不归并事件、不推送、不进精选和日报，也不按时效打分。
抓取失败（公众号风控、页面删除）不自动重试，管理员可以粘贴正文重新收录；模型临时故障由 retry_failed 重试。
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import RawItem
from app.collectors.fulltext import extract_main
from app.collectors.http import FetchError, PoliteClient
from app.collectors.textutil import canonical_url, clean_text
from app.config import settings
from app.llm.client import LlmError, complete_json, embed, load_prompt
from app.models import Article, Source
from app.models.enums import ArticleStatus
from app.pipeline.llm_schemas import KnowledgeOutput, KnowledgeScores
from app.pipeline.tuning import load_tuning

log = logging.getLogger(__name__)

WECHAT_HOST = "mp.weixin.qq.com"
BODY_LIMIT = 20_000
ANALYZE_BODY = 6_000
MAX_ATTEMPTS = 3
MIN_SCORE = 55        # 低于此分不对外展示
FEATURED_SCORE = 75   # 标「精选」
DUP_DISTANCE = 0.06   # bge-m3 余弦距离，低于此视为同一篇（转载）
WEIGHTS = {"depth": 0.3, "practical": 0.35, "accuracy": 0.2, "originality": 0.15}

_WECHAT_KEEP = ("__biz", "mid", "idx", "sn")
_WECHAT_BLOCKED = ("环境异常", "完成验证后即可继续访问", "该内容已被发布者删除", "此内容因违规无法查看",
                   "此内容被投诉且经审核涉嫌侵权", "该公众号已迁移")
_GENERIC_SELECTORS = ("#js_content", "article", "div.article-content", "div.article", "div.TRS_Editor",
                      "div.content", "div.main-content", "#content")
_CT_RE = re.compile(r'var\s+ct\s*=\s*"(\d{10})"')
_NICK_RE = re.compile(r'var\s+nickname\s*=\s*(?:htmlDecode\()?"([^"]+)"')


class ArticleFetchError(Exception):
    pass


@dataclass
class Fetched:
    title: str
    account: str | None
    published_at: datetime | None
    text: str


def article_key(url: str) -> str:
    """去重键。公众号长链接只保留能唯一定位文章的参数，其余（chksm、scene、分享来源）全部去掉。"""
    parts = urlsplit(url.strip())
    if (parts.hostname or "").lower() == WECHAT_HOST and "__biz" in parts.query:
        query = dict(parse_qsl(parts.query))
        kept = urlencode([(k, query[k]) for k in _WECHAT_KEEP if k in query])
        key = urlunsplit(("https", WECHAT_HOST, parts.path, kept, ""))
    else:
        key = canonical_url(url)
    return hashlib.sha256(key.encode()).hexdigest()


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop)
    value = tag.get("content") if tag else None
    return clean_text(value) if isinstance(value, str) else None


def _paragraphs(text: str) -> str:
    """保留段落换行，段内空白压缩。"""
    return "\n".join(line for line in (clean_text(x) for x in text.splitlines()) if line)


def parse_wechat(html: str) -> Fetched:
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one("#js_content")
    if body is None:
        page_text = soup.get_text(" ", strip=True)
        blocked = next((m for m in _WECHAT_BLOCKED if m in page_text), None)
        raise ArticleFetchError(f"公众号页面无法读取正文（{blocked or '页面结构不符'}），请粘贴正文后重新收录")
    title_node = soup.select_one("#activity-name") or soup.select_one("h1")
    title = (clean_text(title_node.get_text()) if title_node else _meta(soup, "og:title")) or "（无标题）"
    name = soup.select_one("#js_name")
    account = clean_text(name.get_text()) if name else None
    if not account and (m := _NICK_RE.search(html)):
        account = m.group(1)
    published = None
    if m := _CT_RE.search(html):
        published = datetime.fromtimestamp(int(m.group(1)), UTC)
    for tag in body(["script", "style"]):
        tag.decompose()
    text = _paragraphs(body.get_text("\n", strip=True))
    if len(text) < 50:
        raise ArticleFetchError("公众号正文为空（可能是纯图片或视频文章），请粘贴正文后重新收录")
    return Fetched(title=title[:300], account=account[:128] if account else None, published_at=published,
                   text=text[:BODY_LIMIT])


def parse_generic(html: str) -> Fetched:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    title = (_meta(soup, "og:title") or (clean_text(h1.get_text()) if h1 else None)
             or (clean_text(soup.title.get_text()) if soup.title else "")) or "（无标题）"
    main = extract_main(html, _GENERIC_SELECTORS)
    if main is None:
        raise ArticleFetchError("没有找到正文（页面可能需要登录或有反爬），请粘贴正文后重新收录")
    site = _meta(soup, "og:site_name")
    return Fetched(title=title[:300], account=site[:128] if site else None, published_at=None,
                   text=main.text[:BODY_LIMIT])


async def fetch_article(client: PoliteClient, url: str) -> Fetched:
    try:
        page = await client.get(url)
    except FetchError as exc:
        raise ArticleFetchError(f"抓取失败：{exc}") from exc
    host = (urlsplit(page.url).hostname or "").lower()
    return parse_wechat(page.text) if host == WECHAT_HOST else parse_generic(page.text)


def _norm_code(s: str) -> str:
    return re.sub(r"[\s\-－—_/／.·]", "", s).upper()


def ground_standards(standards: list[str], text: str) -> list[str]:
    """只保留原文里确实出现过的标准编号（忽略空格、横线、斜杠的写法差异）。"""
    haystack = _norm_code(text)
    out: list[str] = []
    for code in standards:
        norm = _norm_code(code)
        if len(norm) >= 4 and any(ch.isdigit() for ch in norm) and norm in haystack and code not in out:
            out.append(code)
    return out


def knowledge_score(s: KnowledgeScores) -> float:
    return round(sum(getattr(s, k) * w for k, w in WEIGHTS.items()) * 10, 1)


def build_input(article: Article) -> str:
    body = (article.content_text or "").strip()
    return "\n".join([
        f"来源：{article.account or (article.source.name if article.source else '未知')}",
        f"标题：{article.title}",
        f"正文：{body[:ANALYZE_BODY]}",
    ])


async def analyze_article(article: Article, profile: str) -> KnowledgeOutput:
    return await complete_json(
        task="knowledge",
        model=settings.analyze_model,
        system=load_prompt("knowledge").replace("{profile}", profile),
        user=build_input(article),
        schema=KnowledgeOutput,
        max_tokens=1500,
        temperature=0.2,
    )


def apply_knowledge(article: Article, out: KnowledgeOutput) -> None:
    """写回卡片与分数，并决定是否对外展示（不提交）。"""
    article.title_zh = out.title_zh or None
    article.summary = out.summary or None
    article.key_points = out.key_points
    article.scenarios = out.scenarios or None
    article.solution_use = out.solution_use or None
    article.standards = ground_standards(out.standards, f"{article.title}\n{article.content_text or ''}")
    article.domain, article.ktype, article.tags = out.domain, out.ktype, out.tags
    s = out.scores
    article.d_depth, article.d_practical, article.d_accuracy, article.d_original = (
        s.depth, s.practical, s.accuracy, s.originality)
    article.score = knowledge_score(s)
    article.analyzed_at = datetime.now(UTC)
    if not out.relevant:
        article.status, article.status_reason = ArticleStatus.REJECTED.value, "不是电力专业知识"
    elif out.is_promo:
        article.status, article.status_reason = ArticleStatus.REJECTED.value, "营销推广为主"
    elif article.score < MIN_SCORE:
        article.status = ArticleStatus.REJECTED.value
        article.status_reason = f"质量分 {article.score:.0f} 低于 {MIN_SCORE}"
    else:
        article.status, article.status_reason = ArticleStatus.ANALYZED.value, None


def embedding_text(article: Article) -> str:
    return f"{article.title_zh or article.title}\n{article.summary or ''}\n{'；'.join(article.key_points or [])}"


async def find_duplicate(session: AsyncSession, article: Article) -> int | None:
    """同标题，或向量几乎相同的已收录文章（公众号之间互相转载很常见，保留先收录的那篇）。"""
    shown = (ArticleStatus.ANALYZED.value, ArticleStatus.HIDDEN.value)
    same_title = await session.scalar(
        select(Article.id).where(Article.id != article.id, Article.status.in_(shown), Article.title == article.title)
        .order_by(Article.id).limit(1)
    )
    if same_title is not None or article.embedding is None:
        return same_title
    distance = Article.embedding.cosine_distance(article.embedding)
    row = (await session.execute(
        select(Article.id, distance.label("d")).where(
            Article.id != article.id, Article.status.in_(shown), Article.embedding.is_not(None))
        .order_by(distance).limit(1)
    )).first()
    return row.id if row is not None and row.d < DUP_DISTANCE else None


def _fail(article: Article, reason: str, *, retryable: bool) -> None:
    article.status = ArticleStatus.FAILED.value
    article.status_reason = reason[:500]
    article.attempts = article.attempts + 1 if retryable else MAX_ATTEMPTS


async def process_article(session: AsyncSession, client: PoliteClient, article_id: int) -> dict[str, Any]:
    article = await session.get(Article, article_id)
    if article is None or article.status not in (ArticleStatus.NEW, ArticleStatus.FAILED):
        return {"skipped": True}
    if not article.content_text:
        try:
            got = await fetch_article(client, article.url)
        except ArticleFetchError as exc:
            _fail(article, str(exc), retryable=False)
            await session.commit()
            return {"status": article.status, "reason": article.status_reason}
        if article.title in ("", article.url):
            article.title = got.title
        article.account = article.account or got.account
        article.published_at = article.published_at or got.published_at
        article.content_text = got.text
        await session.commit()

    tuning = await load_tuning(session)
    try:
        out = await analyze_article(article, tuning.profile)
    except LlmError as exc:
        _fail(article, str(exc), retryable=exc.retryable)
        await session.commit()
        return {"status": article.status, "reason": article.status_reason}
    apply_knowledge(article, out)

    if article.status == ArticleStatus.ANALYZED:
        try:
            vectors = await embed([embedding_text(article)])
        except LlmError as exc:
            log.warning("知识文章向量化失败，跳过语义去重：%s", exc)
            vectors = None
        if vectors:
            article.embedding = vectors[0]
        if (dup := await find_duplicate(session, article)) is not None:
            article.status, article.duplicate_of = ArticleStatus.DUPLICATE.value, dup
            article.status_reason = f"与 #{dup} 重复"
    await session.commit()
    return {"status": article.status, "score": article.score}


async def upsert_articles(session: AsyncSession, source: Source, raws: list[RawItem]) -> list[int]:
    """信源配置了 target: knowledge 时，采集结果进知识库而不是资讯流。返回新收录的 id。"""
    rows = {}
    for raw in raws:
        key = article_key(raw.url)
        rows[key] = {
            "source_id": source.id, "url": raw.url.strip(), "url_hash": key,
            "title": clean_text(raw.title)[:300], "account": source.name[:128],
            "content_text": clean_text(raw.content_text)[:BODY_LIMIT] if raw.content_text else None,
            "published_at": raw.published_at,
        }
    if not rows:
        return []
    # 冲突（已收录过）的行不会出现在 RETURNING 里
    stmt = insert(Article).values(list(rows.values())).on_conflict_do_nothing(index_elements=[Article.url_hash])
    return list((await session.scalars(stmt.returning(Article.id))).all())
