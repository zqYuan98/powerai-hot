"""电力AI-hot · FastAPI 应用入口。"""
from contextlib import asynccontextmanager
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from api import admin, articles, auth, cards, favorites, jobs, reports, sources, subscriptions, system, threads
from core.auth import require_admin, require_workspace
from core.config import settings
from core.session import validate_security_config
from models import schema
from models.database import SessionLocal, get_db, init_db
from models.seed import seed_research_threads, seed_sources
from scheduler.monitor import start_monitor, stop_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_config(settings)
    init_db()
    db = SessionLocal()
    try:
        seed_sources(db)
        seed_research_threads(db)
        db.commit()
    finally:
        db.close()
    yield
    stop_monitor()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
for router in (articles.router, reports.router, favorites.router, cards.router, sources.router, subscriptions.router, threads.router):
    app.include_router(
        router,
        prefix=settings.api_prefix,
        dependencies=[Depends(require_workspace)],
    )
# Admin routes require an admin session or the legacy X-Admin-Token header.
app.include_router(admin.router, prefix=settings.api_prefix, dependencies=[Depends(require_admin)])
app.include_router(jobs.router, prefix=settings.api_prefix, dependencies=[Depends(require_admin)])
app.include_router(system.router, prefix=settings.api_prefix, dependencies=[Depends(require_admin)])


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "app": settings.app_name, "ai_provider": settings.ai_provider}


@app.get(f"{settings.api_prefix}/rss.xml")
def public_rss(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(schema.Article)
        .join(schema.Source, schema.Article.source_id == schema.Source.id)
        .where(
            schema.Article.curated.is_(True),
            schema.Article.scored.is_(True),
            schema.Article.url.isnot(None),
            schema.Article.source_id.isnot(None),
            schema.Source.status == "已采纳",
            schema.Source.url.like("http%"),
        )
        .order_by(schema.Article.published_at.desc().nullslast(), schema.Article.crawled_at.desc())
        .limit(50)
    ).all()
    items = []
    for article in rows:
        title = escape(article.title or "")
        link = escape(article.url or "")
        summary = escape(article.summary or article.content or "")
        pub = article.published_at or article.crawled_at
        pub_text = pub.strftime("%a, %d %b %Y %H:%M:%S GMT") if pub else ""
        items.append(
            "<item>"
            f"<title>{title}</title>"
            f"<link>{link}</link>"
            f"<guid>{link}</guid>"
            f"<description>{summary}</description>"
            f"<pubDate>{escape(pub_text)}</pubDate>"
            "</item>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{escape(settings.app_name)} 精选</title>"
        f"<link>{escape(settings.app_origin)}</link>"
        "<description>公开来源精选 AI 情报</description>"
        + "".join(items) +
        "</channel></rss>"
    )
    return Response(content=body, media_type="application/rss+xml; charset=utf-8")
