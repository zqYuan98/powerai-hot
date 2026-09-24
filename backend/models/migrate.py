"""轻量迁移：启动时为旧库补缺列（SQLite/PG 兼容的简单 ADD COLUMN）。

正式 Alembic 迁移留到生产 PG 部署时引入。
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from models.schema import normalize_source_name, normalize_source_url

NEW_COLUMNS: dict[str, dict[str, str]] = {
    "articles": {
        "content_html": "TEXT",
        "kind": "VARCHAR(8) DEFAULT '资讯'",
        "meta": "JSON",
        "dim_scores": "JSON",
        "tier": "VARCHAR(8) DEFAULT 'T2'",
        "scored": "BOOLEAN DEFAULT FALSE",
        "embedding": "JSON",
        "cluster_id": "VARCHAR(24)",
        "is_cluster_main": "BOOLEAN DEFAULT TRUE",
        "noise_reason": "VARCHAR(200)",
        "source_external_id": "VARCHAR(200)",
        "ingested_at": "DATETIME",
        "processing_status": "VARCHAR(16) DEFAULT 'processed'",
        "scored_by": "VARCHAR(20) DEFAULT 'unscored'",
        "primary_thread_id": "INTEGER",
        "thread_affinity": "JSON",
        "cross_score": "INTEGER DEFAULT 0",
        "axis": "VARCHAR(8) DEFAULT '弱'",
    },
    "sources": {
        "tier": "VARCHAR(8) DEFAULT 'T2'",
        "last_status": "VARCHAR(16)",
        "last_error": "TEXT",
        "name_key": "VARCHAR(400)",
        "url_key": "VARCHAR(1000)",
    },
}

_SOURCE_UNIQUE_INDEXES = {
    "uq_sources_name_key": "name_key",
    "uq_sources_url_key": "url_key",
}

_ARTICLE_FEED_INDEXES = {
    "ix_articles_feed_latest": ("channel", "scored", "crawled_at", "id"),
    "ix_articles_feed_curated_score": (
        "channel", "curated", "scored", "relevance_score", "crawled_at", "id",
    ),
    "ix_articles_published_at": ("published_at",),
    "ix_articles_processing_status": ("processing_status", "scored_by"),
    "ix_articles_primary_thread": ("primary_thread_id", "scored", "crawled_at"),
}

_JOB_RUN_INDEXES = {
    "ix_job_runs_status_started": ("status", "started_at"),
}

_SOURCE_RUN_INDEXES = {
    "ix_source_runs_job_source": ("job_run_id", "source_id"),
    "ix_source_runs_status": ("transport_status", "parse_status"),
}


def _legacy_key(base: str, source_id: int, used: set[str], limit: int) -> str:
    suffix = f"#legacy-{source_id}"
    candidate = f"{base[: max(1, limit - len(suffix))]}{suffix}"
    counter = 2
    while candidate in used:
        extra = f"-{counter}"
        suffix = f"#legacy-{source_id}{extra}"
        candidate = f"{base[: max(1, limit - len(suffix))]}{suffix}"
        counter += 1
    return candidate


def _backfill_source_keys(engine: Engine) -> None:
    """Populate normalized keys, preserving the first legacy duplicate row."""
    insp = inspect(engine)
    if not insp.has_table("sources"):
        return
    cols = {column["name"] for column in insp.get_columns("sources")}
    if not {"id", "name", "url", "name_key", "url_key"} <= cols:
        return

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, url, name_key, url_key "
                "FROM sources ORDER BY id"
            )
        ).mappings()
        used_names: set[str] = set()
        used_urls: set[str] = set()
        for row in rows:
            name_key = (row["name_key"] or normalize_source_name(row["name"])) or None
            url_key = (row["url_key"] or normalize_source_url(row["url"])) or None
            if name_key and name_key in used_names:
                name_key = _legacy_key(name_key, row["id"], used_names, 400)
            if url_key and url_key in used_urls:
                url_key = _legacy_key(url_key, row["id"], used_urls, 1000)
            if name_key:
                used_names.add(name_key)
            if url_key:
                used_urls.add(url_key)
            conn.execute(
                text(
                    "UPDATE sources SET name_key = :name_key, url_key = :url_key "
                    "WHERE id = :id"
                ),
                {"id": row["id"], "name_key": name_key, "url_key": url_key},
            )


def _ensure_source_unique_indexes(engine: Engine) -> None:
    insp = inspect(engine)
    if not insp.has_table("sources"):
        return
    existing = {index["name"] for index in insp.get_indexes("sources")}
    with engine.begin() as conn:
        for index_name, column in _SOURCE_UNIQUE_INDEXES.items():
            if index_name in existing:
                continue
            conn.execute(
                text(
                    f'CREATE UNIQUE INDEX "{index_name}" '
                    f'ON sources ("{column}")'
                )
            )


def _ensure_article_feed_indexes(engine: Engine) -> None:
    insp = inspect(engine)
    if not insp.has_table("articles"):
        return
    existing = {index["name"] for index in insp.get_indexes("articles")}
    columns = {column["name"] for column in insp.get_columns("articles")}
    with engine.begin() as conn:
        for index_name, index_columns in _ARTICLE_FEED_INDEXES.items():
            if index_name in existing or not set(index_columns) <= columns:
                continue
            quoted = ", ".join(f'"{column}"' for column in index_columns)
            conn.execute(text(f'CREATE INDEX "{index_name}" ON articles ({quoted})'))


def _ensure_run_tables(engine: Engine) -> None:
    from models.database import Base
    from models import schema  # noqa: F401

    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables["job_runs"],
        Base.metadata.tables["source_runs"],
    ])


def _ensure_indexes(engine: Engine, table: str, indexes: dict[str, tuple[str, ...]]) -> None:
    insp = inspect(engine)
    if not insp.has_table(table):
        return
    existing = {index["name"] for index in insp.get_indexes(table)}
    columns = {column["name"] for column in insp.get_columns(table)}
    with engine.begin() as conn:
        for index_name, index_columns in indexes.items():
            if index_name in existing or not set(index_columns) <= columns:
                continue
            quoted = ", ".join(f'"{column}"' for column in index_columns)
            conn.execute(text(f'CREATE INDEX "{index_name}" ON {table} ({quoted})'))


def ensure_columns(engine: Engine) -> None:
    _ensure_run_tables(engine)
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    _backfill_source_keys(engine)
    _ensure_source_unique_indexes(engine)
    _ensure_article_feed_indexes(engine)
    _ensure_indexes(engine, "job_runs", _JOB_RUN_INDEXES)
    _ensure_indexes(engine, "source_runs", _SOURCE_RUN_INDEXES)
