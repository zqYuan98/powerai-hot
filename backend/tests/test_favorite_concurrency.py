"""Concurrency contract for favorite/card creation."""

from concurrent.futures import ThreadPoolExecutor
import threading

from fastapi import BackgroundTasks
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import schema
from models.database import Base


def test_unsupported_dialect_reraises_unrelated_integrity_error(db, monkeypatch):
    from api.favorites import _insert_for_article_once

    db.execute(text("PRAGMA foreign_keys=ON"))
    db.commit()
    monkeypatch.setattr(db.get_bind().dialect, "name", "unsupported")

    with pytest.raises(IntegrityError):
        _insert_for_article_once(db, schema.Favorite, article_id=999_999)


def test_unsupported_dialect_accepts_verified_duplicate(db, monkeypatch):
    from api.favorites import _insert_for_article_once

    article = schema.Article(title="Existing favorite", url="https://example.com/old")
    db.add(article)
    db.flush()
    db.add(schema.Favorite(article_id=article.id))
    db.commit()
    monkeypatch.setattr(db.get_bind().dialect, "name", "unsupported")

    assert _insert_for_article_once(db, schema.Favorite, article.id) is None


def test_concurrent_favorite_requests_create_and_schedule_one_card(
    tmp_path, monkeypatch
):
    from api import favorites

    engine = create_engine(
        f"sqlite:///{(tmp_path / 'favorites.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 15},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        article = schema.Article(title="Concurrent favorite", url="https://example.com")
        db.add(article)
        db.commit()
        article_id = article.id

    # Both old check-then-insert requests must observe that no favorite exists
    # before either is allowed to proceed to its autoflushed INSERT.
    favorite_reads = 0
    favorite_reads_lock = threading.Lock()
    both_read_absent = threading.Barrier(2)

    @event.listens_for(engine, "after_cursor_execute")
    def _synchronize_favorite_reads(_conn, _cursor, statement, *_args):
        nonlocal favorite_reads
        if not statement.lstrip().upper().startswith("SELECT"):
            return
        if "from favorites" not in statement.lower():
            return
        with favorite_reads_lock:
            if favorite_reads >= 2:
                return
            favorite_reads += 1
        both_read_absent.wait(timeout=5)

    monkeypatch.setattr(favorites, "generate_card", lambda _card_id: None)
    start_together = threading.Barrier(2)

    def add_in_independent_request():
        background = BackgroundTasks()
        with Session() as db:
            start_together.wait(timeout=5)
            try:
                result = favorites.add_favorite(article_id, background, db)
            except Exception as exc:
                return 500, exc, background
        return 200, result, background

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: add_in_independent_request(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", _synchronize_favorite_reads)

    assert [status for status, _result, _background in results] == [200, 200]
    assert len({result["card_id"] for _status, result, _background in results}) == 1
    scheduled = [
        task.args[0]
        for _status, _result, background in results
        for task in background.tasks
        if task.func is favorites.generate_card
    ]
    assert scheduled == [results[0][1]["card_id"]]
    with Session() as db:
        assert len(db.scalars(select(schema.Favorite)).all()) == 1
        assert len(db.scalars(select(schema.KnowledgeCard)).all()) == 1

    engine.dispose()
