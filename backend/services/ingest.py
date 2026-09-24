"""统一采集管线（四段式）：

采集(逐采集器容错) → ①预筛(便宜模型) → ②六维评分+内容处理(较强模型)
→ ③代码合成 quality/cross_score/axis → ④代码精选（频道阈值 ∪ 交叉通道）
→ 入库 → 命中订阅通知。

被三处复用：管理后台「立即采集」、内置定时监控、Celery 任务。
"""
from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from analyzer.embedder import embed
from analyzer.enricher import enrich
from analyzer.prefilter import prefilter
from analyzer.prefilter import _rule_based as rule_prefilter
from analyzer.scorer import score
from analyzer.scoring import DIM_KEYS, evaluate
from core.config import settings
from core.constants import CHANNELS
from services.clustering import assign_cluster
from collector.arxiv import ArxivCollector
from collector.aggregator import AggregatorCollector
from collector.aihot import AihotCollector
from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.bjx import BjxCollector
from collector.csg_bidding import SouthernGridBiddingCollector
from collector import fulltext
from collector.frontier import FrontierSnapshotCollector
from collector.gov_procurement import GovProcurementCollector
from collector.github_releases import GitHubReleasesCollector
from collector.hf_papers import HFPapersCollector
from collector.nea import NeaCollector
from collector.rss import RssCollector
from collector.sgcc_news import SgccNewsCollector
from collector.southern_grid import SouthernGridCollector
from core.htmlsanitize import sanitize_html
from models import schema
from services.config_store import get_scoring_config
from services.threads import keyword_affinity, score_for_threads


# 内置采集器名单：API 层据此给 Source 行打 builtin 标记，前端按标记分组展示。
# 新增/改名内置采集器只需改 build_collectors，这里自动跟随。
BUILTIN_SOURCE_NAMES: tuple[str, ...] = (
    BjxCollector.source_name,
    SgccNewsCollector.source_name,
    NeaCollector.source_name,
    SouthernGridCollector.source_name,
    GovProcurementCollector.source_name,
    SouthernGridBiddingCollector.source_name,
    FrontierSnapshotCollector.source_name,
    AihotCollector.source_name,
    AggregatorCollector.source_name,
    GitHubReleasesCollector.source_name,
    ArxivCollector.source_name,
    HFPapersCollector.source_name,
)

ERROR_SUMMARY_LIMIT = 500


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sanitize_error(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ")
    for marker in ("bearer ", "token=", "api_key=", "apikey=", "cookie:", "password="):
        idx = text.lower().find(marker)
        if idx >= 0:
            text = text[:idx] + marker.split("=")[0] + "=[redacted]"
            break
    return text[:ERROR_SUMMARY_LIMIT]


def _canonical_source_url(collector: BaseCollector, raw: RawArticle | None = None) -> str:
    for value in (
        getattr(raw, "source_url", None),
        getattr(collector, "source_url", ""),
        f"https://{collector.domain}" if collector.domain else "",
    ):
        if value:
            return value
    return f"builtin://{collector.source_name}"


def _source_name(collector: BaseCollector, raw: RawArticle | None = None) -> str:
    return (getattr(raw, "source_name", None) or collector.source_name).strip()


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _source_domain(raw: RawArticle, collector: BaseCollector) -> str | None:
    if raw.source_domain:
        return raw.source_domain
    if collector.domain:
        return collector.domain
    if raw.url:
        try:
            return urlsplit(raw.url).netloc.lower() or None
        except ValueError:
            return None
    return None


def _get_or_create_source(db: Session, collector: BaseCollector, raw: RawArticle | None = None) -> schema.Source:
    name = _source_name(collector, raw)
    url = _canonical_source_url(collector, raw)
    name_key = schema.normalize_source_name(name)
    url_key = schema.normalize_source_url(url)
    src = None
    if url_key:
        src = db.scalar(select(schema.Source).where(schema.Source.url_key == url_key))
    if src is None and name_key:
        src = db.scalar(select(schema.Source).where(schema.Source.name_key == name_key))
    if src is None:
        src = db.scalar(select(schema.Source).where(schema.Source.name == name))
    if src is None:
        src = db.scalar(select(schema.Source).where(schema.Source.url == url))
    if src is None:
        is_rss = isinstance(collector, RssCollector)
        src = schema.Source(
            name=name,
            url=url,
            name_key=name_key,
            url_key=url_key,
            type="RSS" if is_rss else "网站",
            status="已采纳",
            submitted_by="seed" if is_rss else "builtin",
            tier=getattr(collector, "tier", "T2") or "T2",
        )
        db.add(src)
        db.flush()
    elif not isinstance(collector, RssCollector) and src.submitted_by in (None, "builtin"):
        src.type = "网站"
        src.submitted_by = "builtin"
    return src


def _coerce_result(value) -> CollectorResult:
    if isinstance(value, CollectorResult):
        return value
    if isinstance(value, list):
        return CollectorResult.ok(items=value)
    return CollectorResult.schema_error(f"collector returned {type(value).__name__}")


def _record_source_run(
    db: Session,
    *,
    job_run: schema.JobRun,
    source: schema.Source | None,
    attempted_at: datetime,
    result: CollectorResult,
) -> None:
    finished = _utcnow_naive()
    newest = None
    for item in result.items:
        item_time = _normalize_dt(item.published_at)
        if item_time is not None and (newest is None or item_time > newest):
            newest = item_time
    db.add(schema.SourceRun(
        job_run_id=job_run.id,
        source_id=source.id if source else None,
        attempted_at=attempted_at,
        finished_at=finished,
        duration_ms=max(0, int((finished - attempted_at).total_seconds() * 1000)),
        transport_status=result.transport_status,
        parse_status=result.parse_status,
        fetched_count=len(result.items),
        newest_item_at=newest,
        error_summary=_sanitize_error(result.error_summary) if result.error_summary else None,
    ))


def _default_run_key(job_name: str) -> str:
    now = _utcnow_naive()
    if "papers" in job_name:
        return f"{job_name}:{now:%Y-%m-%d}"
    window_hour = (now.hour // 2) * 2
    return f"{job_name}:{now:%Y-%m-%d}T{window_hour:02d}"


def _start_job_run(db: Session, job_name: str, run_key: str | None) -> tuple[schema.JobRun, bool]:
    key = run_key or _default_run_key(job_name)
    existing = db.scalar(select(schema.JobRun).where(schema.JobRun.run_key == key))
    if existing is not None:
        return existing, False
    job = schema.JobRun(run_key=key, job_name=job_name, started_at=_utcnow_naive(), status="running")
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(schema.JobRun).where(schema.JobRun.run_key == key))
        if existing is not None:
            return existing, False
        raise
    db.refresh(job)
    return job, True


def _retryable_model_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, RuntimeError):
        message = str(exc).lower()
        if any(marker in message for marker in ("invalid json", "bad json", "format")):
            return False
        return any(marker in message for marker in ("timeout", "timed out", "429", "rate", "temporar", "500", "502", "503", "504"))
    return False


def _retry_model_call(fn, *args, sleep=time.sleep, **kwargs):
    last_exc = None
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= 2 or not _retryable_model_error(exc):
                break
            sleep(min(2 ** attempt, 4))
    raise last_exc


def _model_failure_reason(exc: Exception) -> str:
    """把模型异常压成一行可诊断原因；4xx 带上接口返回体的前 200 字。

    配置类故障（模型名下线、Key 失效、欠费）都是 4xx，永远重试不好，
    必须和「超时/限流」这种自愈故障区分开，否则只能看到 scored_by=rule
    却不知道为什么 —— 2026-07-24 deepseek-chat 下线就是这样静默降级了 19 小时。
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status = exc.response.status_code
        body = _sanitize_error(exc.response.text)[:200]
        kind = "配置/额度故障（不会自愈）" if 400 <= status < 500 and status != 429 else "临时故障"
        return f"HTTP {status} {kind}: {body}"
    return f"{type(exc).__name__}: {_sanitize_error(exc)[:200]}"



def _try_fulltext(article: schema.Article, stats: dict) -> None:
    """预筛通过后、评分之前补抓正文。

    放在这个位置有两个理由：预筛之前抓会给噪音条目白花一次请求；
    评分之后抓则这一轮的 summary/评分仍然只见标题，等于白抓。
    抓不到不阻断——正文是增强项，不是必需项。
    """
    if article.content or not fulltext.is_supported(article.url):
        return
    try:
        result = fulltext.fetch_fulltext(article.url)
    except Exception as exc:
        logging.getLogger("ingest").warning(
            "正文回捞异常 article=%s %s", article.id, _sanitize_error(exc)
        )
        return
    meta = dict(article.meta or {})
    if not result:
        meta["fulltext_status"] = "miss"
        article.meta = meta
        stats["fulltext_miss"] = stats.get("fulltext_miss", 0) + 1
        return
    article.content = result["content"]
    if result.get("content_html") and not article.content_html:
        article.content_html = result["content_html"]
    meta["fulltext_status"] = "ok"
    meta["fulltext_chars"] = result["chars"]
    article.meta = meta
    stats["fulltext_ok"] = stats.get("fulltext_ok", 0) + 1


def _note_model_failure(stats: dict, stage: str, exc: Exception) -> None:
    """记录模型故障：日志 + 去重收集到 stats，供 job_run.error_summary 展示。"""
    reason = _model_failure_reason(exc)
    permanent = (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response is not None
        and 400 <= exc.response.status_code < 500
        and exc.response.status_code != 429
    )
    log = logging.getLogger("ingest")
    (log.error if permanent else log.warning)("模型调用失败 stage=%s %s", stage, reason)
    stats.setdefault("model_errors", {})[f"{stage}: {reason}"] = (
        stats.setdefault("model_errors", {}).get(f"{stage}: {reason}", 0) + 1
    )


def _rule_score(title: str) -> dict:
    text = title.lower()
    hits = [kw for kw in ["电力", "巡检", "ocr", "视觉", "大模型", "llm", "多模态", "检测", "智能"] if kw in text or kw in title]
    base = 76 if hits else 62
    return {
        "dims": {key: base for key in DIM_KEYS},
        "reason": f"规则回退命中：{'、'.join(hits[:3])}" if hits else "规则回退：模型不可用。",
    }


def _apply_thread_score(article: schema.Article, score_data: dict, threads: list[schema.ResearchThread], cfg: dict) -> int:
    affinity = score_data.get("affinity")
    if not isinstance(affinity, dict):
        affinity = keyword_affinity(article.title, article.summary, article.content, threads)
    result = score_for_threads(
        score_data["dims"], affinity, threads,
        tier=article.tier or "T2", kind=article.kind or "资讯",
        tier_coeff=cfg.get("tier_coeff"), kind_coeff=cfg.get("kind_coeff"),
    )
    article.thread_affinity = {str(key): int(value) for key, value in affinity.items()}
    article.primary_thread_id = result.primary_thread_id
    threshold = cfg.get("horizon_threshold", 70)
    if result.primary_thread_id is not None:
        threshold = cfg.get("thread_thresholds", {}).get(str(result.primary_thread_id), 60)
    article.curated = result.learn_score >= int(threshold)
    return result.learn_score


def _has_custom_fallback() -> bool:
    return bool(settings.custom_api_url and settings.custom_model)


def source_is_crawlable(src: schema.Source) -> bool:
    """DB 信源是否会被 build_collectors 变成采集器（网站类暂无解析器，不抓取）。"""
    return (
        src.type in ("RSS", "公众号")
        and bool(src.url)
        and src.submitted_by != "builtin"
    )


def build_collectors(db: Session, limit: int = 20, group: str = "all") -> list[BaseCollector]:
    """内置采集器 + 数据库中「已采纳」的 RSS/公众号源；按调度分组过滤。

    group: news(每小时) | papers(每日) | all
    """
    collectors: list[BaseCollector] = [
        BjxCollector(limit=limit),
        SgccNewsCollector(limit=limit),
        NeaCollector(limit=limit),
        SouthernGridCollector(limit=limit),
        GovProcurementCollector(limit=limit),
        SouthernGridBiddingCollector(limit=limit),
        # FrontierSnapshotCollector（GitHub Trending 快照）已停用 2026-07-26：
        # 实测 14 条里 43% 判噪音、零精选。它抓的是大众 GitHub 热度，与本产品
        # 「电力×视觉」方向正交；同类需求由 GitHubReleasesCollector 的 23 个
        # 人工挑定仓库覆盖，那批信噪比全库最高（PaddleOCR 10/10 精选）。
        # FrontierSnapshotCollector(limit=limit),
        AihotCollector(limit=limit),
        # AggregatorCollector 已停用（2026-07-25）。它是 TopHub / TechURLs / NewsNow /
        # Info Flow / 新智元 / 微信公众号 这批 T1.5 热榜源的唯一产出来源，生产实测
        # 69 条全部未入精选、最高分 43（阈值 60），且不是分级系数问题——系数拉到 1.0
        # 也是 0 条。热榜聚合的是「大众科技热度」，与本产品的电力×视觉方向正交。
        # 需要恢复时取消注释即可，采集器本身保留。
        # AggregatorCollector(limit=limit),
        # 23 个仓 × 每仓 3 条 = 69 个候选；limit 给足才不会把靠后的仓挤掉
        # （入库仍受 run_ingest 的 max_total 与 URL 去重约束，不会撑爆单轮预算）。
        GitHubReleasesCollector(limit=max(limit, 70), per_repo_limit=3),
        ArxivCollector(limit=max(limit, 30)),
        HFPapersCollector(limit=max(limit, 30)),
    ]
    rows = db.scalars(select(schema.Source).where(schema.Source.status == "已采纳")).all()
    for s in rows:
        if source_is_crawlable(s):
            collectors.append(RssCollector(s.url, source_name=s.name, limit=limit,
                                           tier=s.tier or "T2"))
    if group != "all":
        collectors = [c for c in collectors if c.group == group]
    return collectors


def _record_health(db: Session, collector: BaseCollector, *, ok: bool, error: str = "") -> None:
    src = db.scalar(select(schema.Source).where(schema.Source.name == collector.source_name))
    if src is None:
        return
    # UTC（naive，与 Article.crawled_at 的 SQLite CURRENT_TIMESTAMP 同基准）；前端统一按 UTC 解析后转本地
    src.last_crawled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    src.last_status = "ok" if ok else "error"
    src.last_error = error[:500] if error else None


RESCORE_PER_ROUND = 6  # 每轮顺带补打分的积压条数：控成本，按小时轮次一天也能消化 ~140 条


def rescore_pending(db: Session, cfg: dict, limit: int = RESCORE_PER_ROUND) -> int:
    """补打分积压：预筛/评分曾因模型故障失败的条目（scored=0 且非噪音）会永远无分——
    进不了精选、沉在列表底部，且此前没有任何机制重试（"可重试"只是入库时的注释）。
    每轮采集末尾补最近几条；单条尝试 3 次仍失败就放弃，不再烧模型钱。

    规则打分的条目同样要捞：模型故障期间 scored_by 会落成 'rule'，但 scored=True，
    旧实现的 scored=False 条件永远选不到它们 —— 2026-07-24 deepseek-chat 下线那次
    留下 156 条永久带着规则分（base≈43，任何 tier 都进不了精选）沉底的文章。"""
    # 与 process_pending 用同一套研究方向，否则补打分出来的 curated 口径会和入库时不一致
    threads = list(db.scalars(
        select(schema.ResearchThread)
        .where(schema.ResearchThread.status == "active")
        .order_by(schema.ResearchThread.id)
    ))
    candidates = db.scalars(
        select(schema.Article)
        .where(
            schema.Article.noise_reason.is_(None),
            or_(
                schema.Article.scored.is_(False),
                schema.Article.scored_by == "rule",
            ),
        )
        .order_by(schema.Article.crawled_at.desc())
        .limit(limit * 5)
    ).all()
    done = 0
    for article in candidates:
        if done >= limit:
            break
        attempts = int((article.meta or {}).get("rescore_attempts", 0))
        if attempts >= 3:
            continue
        article.meta = {**(article.meta or {}), "rescore_attempts": attempts + 1}
        try:
            pf = prefilter(article.title, article.content or "")
        except Exception:
            db.rollback()
            break  # 模型不可用，本轮到此为止，下轮再试（attempts 不落库）
        if not pf["relevant"] and not bool((article.meta or {}).get("trusted_relevance")):
            article.noise_reason = f"预筛判定无关（{pf['domain']}）"
            article.curated = False
            article.hot = False
            article.scored = False
            article.scored_by = "unscored"
        else:
            if not bool((article.meta or {}).get("lock_channel")):
                article.channel = pf.get("channel") or article.channel
            need_enrich = not article.summary
            with ThreadPoolExecutor(max_workers=2) as ex:
                fut_score = ex.submit(score, article.title, article.content or "")
                fut_enrich = ex.submit(enrich, article.title, article.content or "") if need_enrich else None
            try:
                s = fut_score.result()
                verdict = evaluate(s["dims"], tier=article.tier or "T2", kind=article.kind,
                                   channel=article.channel, config=cfg)
                article.dim_scores = s["dims"]
                article.recommend_reason = s["reason"]
                article.cross_score = verdict["cross_score"]
                article.axis = verdict["axis"]
                if threads:
                    article.relevance_score = _apply_thread_score(article, s, threads, cfg)
                    article.hot = article.relevance_score >= cfg["hot_score"]
                else:
                    article.relevance_score = verdict["quality"]
                    article.curated = verdict["curated"]
                    article.hot = verdict["hot"]
                article.scored = True
                # 必须改写 scored_by：否则规则分条目补打分成功后仍标着 'rule'，
                # 会被候选查询反复选中，白烧 3 次重试额度才罢休。
                article.scored_by = "primary_model"
            except Exception as exc:
                # 评分仍失败：attempts+1 已记，达 3 次后不再重试
                logging.getLogger("ingest").warning(
                    "补打分失败 article=%s %s", article.id, _model_failure_reason(exc)
                )
            if fut_enrich is not None:
                try:
                    e = fut_enrich.result()
                    article.summary = e["summary"]
                    article.tags = e["tags"]
                    article.org = e["org"]
                    if e["title_zh"]:
                        article.meta = {**(article.meta or {}), "title_zh": e["title_zh"]}
                except Exception:
                    pass
        try:
            db.commit()
        except OperationalError:
            db.rollback()
            break
        if article.scored or article.noise_reason:
            done += 1
    return done


def count_unscored_backlog(db: Session) -> int:
    """尚未成功打分、又不是噪音的存量条目数（补打分队列长度）。"""
    from sqlalchemy import func

    return int(db.scalar(
        select(func.count()).select_from(schema.Article)
        .where(schema.Article.scored.is_(False), schema.Article.noise_reason.is_(None))
    ) or 0)


def ingest_once(
    db: Session,
    *,
    collectors: list[BaseCollector] | None = None,
    limit: int = 20,
    group: str = "all",
    max_total: int = 40,
    max_per_source: int = 6,
    run_key: str | None = None,
) -> dict:
    """Fetch, commit raw articles, then process pending rows.

    max_total bounds raw inserts per run. AI/model work happens only after the
    raw Article rows have committed, so model failures cannot roll back supply.
    """
    job_run, started = _start_job_run(db, f"ingest-{group}", run_key)
    if not started:
        return {
            "job_status": "skipped",
            "fetched": 0,
            "inserted": 0,
            "curated": 0,
            "skipped_duplicate": 0,
            "prefiltered_out": 0,
            "analyze_errors": 0,
            "collector_errors": [],
            "capped": False,
            "rescored": 0,
            "rescore_backlog": count_unscored_backlog(db),
            "samples": [],
        }

    collectors = collectors or build_collectors(db, limit, group=group)
    random.shuffle(collectors)
    fetched = inserted = curated_n = skipped = prefiltered_out = analyze_errors = 0
    collector_errors: list[str] = []
    samples: list[dict] = []
    successful: list[tuple[BaseCollector, CollectorResult]] = []

    seen_hashes: set[str] = set()  # 批内去重（session 关闭 autoflush，查询看不到未提交行）

    for collector in collectors:
        attempted_at = _utcnow_naive()
        source = None
        try:
            source = _get_or_create_source(db, collector)
            db.commit()
            result = _coerce_result(collector.fetch())
        except Exception as e:  # 单个采集器失败不影响其他（记录健康状态）
            collector_errors.append(collector.source_name)
            _record_health(db, collector, ok=False, error=str(e))
            result = CollectorResult.network_error(_sanitize_error(e))
            source = source or db.scalar(select(schema.Source).where(schema.Source.name == collector.source_name))
            _record_source_run(db, job_run=job_run, source=source, attempted_at=attempted_at, result=result)
            db.commit()
            continue
        _record_source_run(db, job_run=job_run, source=source, attempted_at=attempted_at, result=result)
        if result.transport_status != "ok" or result.parse_status in {"schema_error", "parse_error"}:
            collector_errors.append(collector.source_name)
            _record_health(db, collector, ok=False, error=result.error_summary or result.parse_status)
            db.commit()
            continue
        _record_health(db, collector, ok=True)
        db.commit()
        fetched += len(result.items)
        successful.append((collector, result))

    iterators = [(collector, iter(result.items)) for collector, result in successful]
    source_inserted = {id(collector): 0 for collector, _result in successful}
    while inserted < max_total:
        progressed = False
        for collector, iterator in iterators:
            if source_inserted[id(collector)] >= max_per_source:
                continue
            while True:
                try:
                    raw = next(iterator)
                    progressed = True
                except StopIteration:
                    break
                if raw.url_hash in seen_hashes or db.scalar(
                    select(schema.Article).where(schema.Article.url_hash == raw.url_hash)
                ):
                    skipped += 1
                    continue
                seen_hashes.add(raw.url_hash)

                article_source = _get_or_create_source(db, collector, raw)
                raw_meta = dict(raw.meta or {})
                if raw.provenance:
                    raw_meta["provenance"] = raw.provenance
                article = schema.Article(
                    title=raw.title,
                    content=raw.content,
                    content_html=(sanitize_html(raw.content_html) or None) if raw.content_html else None,
                    channel=raw.channel,
                    kind=raw.kind,
                    meta=raw_meta or None,
                    tier=collector.tier,
                    source_id=article_source.id,
                    source_domain=_source_domain(raw, collector),
                    source_external_id=raw.source_external_id,
                    url=raw.url,
                    url_hash=raw.url_hash,
                    published_at=_normalize_dt(raw.published_at),
                    published_label=raw.published_label,
                    scored=False,
                    processing_status="pending",
                    scored_by="unscored",
                    ingested_at=_utcnow_naive(),
                )
                try:
                    db.add(article)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    skipped += 1
                    continue
                except OperationalError:  # 锁超时等：跳过当前条，不中断整批采集
                    db.rollback()
                    analyze_errors += 1
                    continue

                inserted += 1
                source_inserted[id(collector)] += 1
                if len(samples) < 5:
                    samples.append({"title": raw.title[:40],
                                    "score": article.relevance_score,
                                    "channel": article.channel})
                break
            if inserted >= max_total:
                break
        if not progressed:
            break

    db.commit()
    processing = process_pending(db, limit=max_total + RESCORE_PER_ROUND)
    curated_n = processing.get("selected", 0)
    prefiltered_out = processing.get("prefiltered_out", 0)
    analyze_errors = processing.get("errors", 0)
    rescored = processing.get("processed_existing", 0)
    status = "ok"
    if collector_errors or analyze_errors:
        status = "degraded" if inserted or fetched else "failed"
    job_run.finished_at = _utcnow_naive()
    job_run.status = status
    job_run.fetched = fetched
    job_run.inserted = inserted
    job_run.selected = curated_n
    job_run.model_count = processing.get("model_count", 0)
    job_run.fallback_model_count = processing.get("fallback_model_count", 0)
    job_run.rule_count = processing.get("rule_count", 0)
    job_run.source_failures = len(collector_errors)
    # 采集器故障和模型故障都要进 error_summary —— 只记采集器时，模型全挂（rule_count
    # 拉满、selected 归零）在运维界面上看不出任何原因。
    model_errors = [f"{reason} ×{count}" for reason, count in processing.get("model_errors", {}).items()]
    all_errors = list(collector_errors) + model_errors
    job_run.error_summary = _sanitize_error("; ".join(all_errors)) if all_errors else None
    job_run.metadata_json = {
        "group": group,
        "capped": inserted >= max_total,
        "model_errors": model_errors,
        "fulltext_ok": processing.get("fulltext_ok", 0),
        "fulltext_miss": processing.get("fulltext_miss", 0),
    }
    db.commit()
    return {
        "job_status": status,
        "fetched": fetched,
        "inserted": inserted,
        "curated": curated_n,
        "skipped_duplicate": skipped,
        "prefiltered_out": prefiltered_out,
        "analyze_errors": analyze_errors,
        "collector_errors": collector_errors,
        "capped": inserted >= max_total,
        "rescored": rescored,
        "rescore_backlog": count_unscored_backlog(db),
        "samples": samples,
    }


def process_pending(db: Session, *, limit: int = RESCORE_PER_ROUND) -> dict:
    cfg = get_scoring_config(db)
    active_threads = list(db.scalars(
        select(schema.ResearchThread).where(schema.ResearchThread.status == "active").order_by(schema.ResearchThread.id)
    ))
    sub = db.scalar(select(schema.Subscription).where(schema.Subscription.user_id == "me"))
    keywords = sub.keywords if sub else []
    rows = db.scalars(
        select(schema.Article)
        .where(schema.Article.processing_status.in_(("pending", "degraded")))
        .order_by(schema.Article.ingested_at.desc(), schema.Article.id.desc())
        .limit(limit)
    ).all()
    stats = {
        "processed": 0,
        "processed_existing": 0,
        "selected": 0,
        "prefiltered_out": 0,
        "model_count": 0,
        "fallback_model_count": 0,
        "rule_count": 0,
        "errors": 0,
    }
    for article in rows:
        was_new = article.processing_status == "pending"
        prefilter_degraded = False
        try:
            pf = _retry_model_call(prefilter, article.title, article.content or "")
        except Exception as exc:
            pf = rule_prefilter(article.title)
            prefilter_degraded = True
            stats["errors"] += 1
            _note_model_failure(stats, "prefilter", exc)
        # trusted_relevance：信源本身就是人工挑定的强相关清单（如 23 个 AI 仓库的
        # GitHub Releases），发布标题常是「v0.26.0」「Marker 2.0.0」这类无语义串，
        # 通用相关性预筛只会误杀。这类条目跳过相关性闸门，仍照常走六维评分。
        if not pf["relevant"] and not bool((article.meta or {}).get("trusted_relevance")):
            article.noise_reason = f"预筛判定无关（{pf['domain']}）"
            article.curated = False
            article.hot = False
            article.scored = False
            article.processing_status = "processed"
            article.scored_by = "unscored"
            stats["prefiltered_out"] += 1
            db.commit()
            continue

        if not bool((article.meta or {}).get("lock_channel")):
            article.channel = pf.get("channel") or article.channel
        _try_fulltext(article, stats)
        scored_by = "primary_model"
        score_data = None
        enrich_data = None
        primary_failed = False

        try:
            if prefilter_degraded:
                primary_failed = True
            else:
                with ThreadPoolExecutor(max_workers=2) as ex:
                    fut_score = ex.submit(_retry_model_call, score, article.title, article.content or "")
                    fut_enrich = ex.submit(_retry_model_call, enrich, article.title, article.content or "")
                try:
                    score_data = fut_score.result()
                except Exception as exc:
                    primary_failed = True
                    _note_model_failure(stats, "scorer", exc)
                try:
                    enrich_data = fut_enrich.result()
                except Exception as exc:
                    stats["errors"] += 1
                    _note_model_failure(stats, "enricher", exc)
        except Exception as exc:
            primary_failed = True
            _note_model_failure(stats, "scorer", exc)

        if primary_failed and not prefilter_degraded and _has_custom_fallback():
            try:
                score_data = _retry_model_call(score, article.title, article.content or "", provider="custom")
                if enrich_data is None:
                    enrich_data = _retry_model_call(enrich, article.title, article.content or "", provider="custom")
                scored_by = "fallback_model"
            except Exception:
                score_data = None
        if score_data is None:
            score_data = _rule_score(article.title)
            scored_by = "rule"

        if enrich_data is not None:
            article.summary = enrich_data["summary"]
            article.tags = enrich_data["tags"]
            article.org = enrich_data["org"]
            if enrich_data.get("title_zh"):
                article.meta = {**(article.meta or {}), "title_zh": enrich_data["title_zh"]}
        elif scored_by == "rule":
            article.summary = article.summary or (article.content or article.title)[:200]
            article.tags = article.tags or []
            article.org = article.org or "行业"

        if score_data is None:
            article.processing_status = "degraded"
            stats["errors"] += 1
            db.commit()
            continue

        verdict = evaluate(score_data["dims"], tier=article.tier or "T2",
                           kind=article.kind or "资讯", channel=article.channel, config=cfg)
        # 双轴是内容属性，两条链路都要落库（研究方向链路原本只算 learn_score）
        article.cross_score = verdict["cross_score"]
        article.axis = verdict["axis"]
        if active_threads:
            quality = _apply_thread_score(article, score_data, active_threads, cfg)
            article.relevance_score = quality
            article.hot = quality >= cfg["hot_score"]
        else:
            article.relevance_score = verdict["quality"]
            article.curated = verdict["curated"]
            article.hot = verdict["hot"]
        # 规则分一律不进精选。旧实现给规则分条目直接 curated=True + quality=60，
        # 于是 2026-07-24 模型故障期间精选池被灌进大量从未经模型评判的条目
        # （修复后精选数 39→35，就是这批假分被清掉）。规则分只保底排序，
        # 等 rescore_pending 用模型补回来再决定是否精选。
        if scored_by == "rule":
            article.curated = False
            article.hot = False
        article.dim_scores = score_data["dims"]
        article.recommend_reason = score_data.get("reason")
        article.scored = True
        article.scored_by = scored_by
        article.processing_status = "processed"

        if scored_by == "primary_model":
            stats["model_count"] += 1
        elif scored_by == "fallback_model":
            stats["fallback_model_count"] += 1
        elif scored_by == "rule":
            stats["rule_count"] += 1
        if article.curated:
            stats["selected"] += 1
            if any(k in article.title for k in keywords):
                _notify_keyword_hit(article)

        try:
            vec = embed(f"{article.title}。{article.summary or ''}") if article.scored else None
        except Exception:
            vec = None
        if vec:
            article.embedding = vec
        try:
            assign_cluster(db, article, threshold=cfg.get("cluster_threshold", 0.82))
        except Exception as exc:
            logging.getLogger("ingest").warning("cluster assignment failed: %s", _sanitize_error(exc))
            stats["errors"] += 1
        db.commit()
        stats["processed"] += 1
        if not was_new:
            stats["processed_existing"] += 1
    return stats


def _notify_keyword_hit(article: schema.Article) -> None:
    """精选且命中订阅关键词 → 推飞书群（未配置 webhook 则静默跳过）。"""
    url = settings.feishu_webhook_url
    if not url:
        return
    title = (article.meta or {}).get("title_zh") or article.title
    text = f"【精选命中】{title}\n{article.recommend_reason or ''}\n{article.url or ''}"
    try:
        httpx.post(url, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
    except Exception as e:  # 推送失败不影响采集
        logging.getLogger("ingest").warning("飞书推送失败: %s", e)
