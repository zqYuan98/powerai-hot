from datetime import datetime

from models import schema
from services.digest import build_daily_digest


def test_daily_digest_groups_active_threads_and_horizon_with_three_item_cap(db):
    thread = schema.ResearchThread(
        name="文档理解", description="文档解析", keywords=["OCR"], weight=1.0, status="active"
    )
    db.add(thread)
    db.flush()
    db.add_all([
        schema.Article(title=f"OCR {score}", primary_thread_id=thread.id, relevance_score=score, curated=True, scored=True)
        for score in (99, 98, 97, 96)
    ])
    db.add(schema.Article(title="通识", relevance_score=88, curated=True, scored=True))
    db.commit()

    report = build_daily_digest(db, now=datetime(2026, 7, 24, 7, 0))

    assert report.content_json["sections"] == [
        {"name": "文档理解", "article_ids": [1, 2, 3]},
        {"name": "视野", "article_ids": [5]},
    ]
