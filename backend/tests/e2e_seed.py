"""Create deterministic data for Playwright without touching the developer database."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import SessionLocal, init_db
from models import schema


def run() -> None:
    # This script is only used by the isolated E2E webServer.  Refuse to remove
    # anything except the explicitly named ignored database file.
    db_path = Path(__file__).resolve().parents[2] / "backend" / ".e2e" / "powerai-e2e.db"
    db_path.parent.mkdir(exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ.setdefault("DATABASE_URL", "sqlite:///./.e2e/powerai-e2e.db")
    init_db()
    db = SessionLocal()
    try:
        source = schema.Source(
            name="E2E 官方来源", url="https://example.com/e2e", type="网站", status="已采纳",
            name_key=schema.normalize_source_name("E2E 官方来源"),
            url_key=schema.normalize_source_url("https://example.com/e2e"),
        )
        db.add(source)
        db.flush()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        article = schema.Article(
            title="唯一检索目标情报", content="隔离测试文章", summary="E2E summary",
            tags=["E2E", "唯一检索目标"], channel="行业动态", source_id=source.id,
            url="https://example.com/e2e/article", url_hash="e2e-article-hash",
            published_label="刚刚", published_at=now, crawled_at=now,
            curated=True, scored=True, relevance_score=90, is_cluster_main=True,
        )
        paged_articles = [
            schema.Article(
                title=f"E2E 分页情报 {index:02d}", content="分页隔离测试", summary=f"分页摘要 {index}",
                tags=["E2E", "分页"], channel="行业动态", source_id=source.id,
                url=f"https://example.com/e2e/page-{index}", url_hash=f"e2e-page-{index}",
                published_at=now - timedelta(minutes=index + 1),
                crawled_at=now - timedelta(minutes=index + 1),
                curated=True, scored=True, relevance_score=80, is_cluster_main=True,
            )
            for index in range(65)
        ]
        db.add_all([article, *paged_articles])
        db.flush()
        db.add(schema.Favorite(article_id=article.id))
        db.add(schema.KnowledgeCard(article_id=article.id, category="电力AI应用", problem="E2E 问题", method="E2E 方法", conclusion="E2E 结论", status="完成"))
        db.add_all([
            schema.Report(type="daily", title="E2E 今日情报", content_md="# E2E", status="完成"),
            schema.Report(type="topic", title="E2E 失败主题", topic="E2E", status="失败"),
            schema.Subscription(user_id="me", keywords=["E2E"], notify_in_app=True),
        ])
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
