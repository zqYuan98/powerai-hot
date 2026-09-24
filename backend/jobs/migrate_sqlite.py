"""Repeatable SQLite-to-target database migration."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import ARRAY, JSON, Boolean, DateTime, MetaData, create_engine, event, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql import and_
from sqlalchemy.orm import sessionmaker

from models import schema  # noqa: F401
from models.database import Base, engine as default_engine
from models.migrate import ensure_columns

TABLE_ORDER = [
    "sources",
    "articles",
    "subscriptions",
    "scoring_config",
    "reports",
    "favorites",
    "knowledge_cards",
    "job_runs",
    "source_runs",
]


def _row_payload(row: Any) -> dict:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def _normalized_domain(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
    except ValueError:
        return None
    host = (parsed.hostname or "").strip(".").casefold()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _json_value(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _bool_value(value: Any) -> bool | None | Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "true", "t", "yes", "y"}:
            return True
        if lowered in {"0", "false", "f", "no", "n"}:
            return False
    return value


def _datetime_value(value: Any) -> datetime | None | Any:
    if value is None:
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return _datetime_value(datetime.fromisoformat(stripped.replace("Z", "+00:00")))
        except ValueError:
            return value
    return value


def _coerce_for_target(target_column: Any, value: Any) -> Any:
    column_type = target_column.type
    if isinstance(column_type, (JSON, ARRAY)):
        return _json_value(value)
    if isinstance(column_type, Boolean):
        return _bool_value(value)
    if isinstance(column_type, DateTime):
        return _datetime_value(value)
    return value


def _coerce_payload(table: Any, payload: dict) -> dict:
    return {key: _coerce_for_target(table.c[key], value) for key, value in payload.items()}


def _table_count(bind: Engine | Connection, table_name: str) -> int:
    insp = inspect(bind)
    if not insp.has_table(table_name):
        return 0
    if isinstance(bind, Engine):
        with bind.connect() as conn:
            return int(conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0)
    return int(bind.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0)


def _same_row(existing: dict, incoming: dict, table_name: str) -> bool:
    for key, value in incoming.items():
        if table_name == "articles" and key == "source_id" and value is None and existing.get(key) is not None:
            continue
        existing_value = existing.get(key)
        if isinstance(existing_value, datetime) or isinstance(value, datetime):
            existing_value = _datetime_value(existing_value)
            value = _datetime_value(value)
        if existing_value != value:
            return False
    return True


def _pk_where(table: Any, payload: dict) -> Any | None:
    pk_columns = list(table.primary_key.columns)
    if not pk_columns:
        return None
    clauses = []
    for column in pk_columns:
        if column.name not in payload:
            return None
        clauses.append(column == payload[column.name])
    return and_(*clauses)


def _reset_pg_sequence(conn: Connection, table_name: str) -> None:
    if conn.dialect.name != "postgresql":
        return
    table = Base.metadata.tables.get(table_name)
    if table is None or "id" not in table.c:
        return
    sequence_name = conn.execute(
        text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
        {"table_name": table_name},
    ).scalar()
    if not sequence_name:
        return
    conn.execute(
        text(
            "SELECT setval(:sequence_name, "
            f"COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 1), true)"
        ),
        {"sequence_name": sequence_name},
    )


def _source_engine(source_file: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///file:{source_file.as_posix()}?mode=ro&uri=true",
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _readonly(dbapi_conn, _record):  # pragma: no cover - verified through migration tests
        dbapi_conn.execute("PRAGMA query_only=ON")

    return engine


def _backfill_article_sources_by_domain(conn: Connection) -> dict:
    stats = {
        "articles_source_id_by_domain": 0,
        "articles_source_id_ambiguous": 0,
        "articles_source_id_unmatched": 0,
    }
    insp = inspect(conn)
    if not insp.has_table("sources") or not insp.has_table("articles"):
        return stats
    article_columns = {column["name"] for column in insp.get_columns("articles")}
    if not {"id", "source_id", "source_domain", "url"} <= article_columns:
        return stats

    source_rows = conn.execute(text("SELECT id, url FROM sources WHERE url IS NOT NULL")).mappings().all()
    domain_to_ids: dict[str, set[int]] = {}
    for row in source_rows:
        domain = _normalized_domain(row["url"])
        if not domain:
            continue
        domain_to_ids.setdefault(domain, set()).add(int(row["id"]))

    article_rows = conn.execute(
        text(
            "SELECT id, source_domain, url FROM articles "
            "WHERE source_id IS NULL AND (source_domain IS NOT NULL OR url IS NOT NULL)"
        )
    ).mappings().all()
    for row in article_rows:
        domain = _normalized_domain(row["source_domain"]) or _normalized_domain(row["url"])
        if not domain:
            stats["articles_source_id_unmatched"] += 1
            continue
        candidates = domain_to_ids.get(domain, set())
        if len(candidates) == 1:
            conn.execute(
                text("UPDATE articles SET source_id = :source_id WHERE id = :id AND source_id IS NULL"),
                {"source_id": next(iter(candidates)), "id": row["id"]},
            )
            stats["articles_source_id_by_domain"] += 1
        elif len(candidates) > 1:
            stats["articles_source_id_ambiguous"] += 1
        else:
            stats["articles_source_id_unmatched"] += 1
    return stats


def _relationship_checks(conn: Connection) -> dict:
    checks = {}
    checks["orphan_articles"] = int(conn.execute(text(
        "SELECT COUNT(*) FROM articles a LEFT JOIN sources s ON a.source_id = s.id "
        "WHERE a.source_id IS NOT NULL AND s.id IS NULL"
    )).scalar() or 0)
    checks["orphan_favorites"] = int(conn.execute(text(
        "SELECT COUNT(*) FROM favorites f LEFT JOIN articles a ON f.article_id = a.id "
        "WHERE a.id IS NULL"
    )).scalar() or 0)
    checks["orphan_knowledge_cards"] = int(conn.execute(text(
        "SELECT COUNT(*) FROM knowledge_cards k LEFT JOIN articles a ON k.article_id = a.id "
        "WHERE a.id IS NULL"
    )).scalar() or 0)
    return checks


def _blocking_failures(summary: dict) -> dict:
    conflict_tables = [
        table_name
        for table_name, table_summary in summary["tables"].items()
        if table_summary.get("conflicts", 0) > 0
    ]
    count_mismatch_tables = [
        table_name
        for table_name, table_summary in summary["tables"].items()
        if summary["post_counts"].get(table_name) != table_summary.get("expected_post_count")
    ]
    relationship_failures = {
        key: value for key, value in summary["relationship_checks"].items() if value
    }
    return {
        "conflict_tables": conflict_tables,
        "count_mismatch_tables": count_mismatch_tables,
        "relationship_failures": relationship_failures,
    }


def migrate_sqlite_to_database(source_path: str, target_engine: Engine = default_engine) -> dict:
    source_file = Path(source_path)
    if not source_file.exists():
        raise FileNotFoundError(source_path)

    src_engine = _source_engine(source_file)
    Base.metadata.create_all(bind=target_engine)
    ensure_columns(target_engine)
    source_metadata = MetaData()
    source_metadata.reflect(bind=src_engine)

    summary = {
        "source": str(source_file),
        "pre_counts": {name: _table_count(target_engine, name) for name in TABLE_ORDER},
        "tables": {},
        "post_counts": {},
        "relationship_checks": {},
        "backfill": {},
        "blocking_failures": {},
        "gate_passed": False,
    }

    try:
        with src_engine.connect() as src_conn, target_engine.connect() as dst_conn:
            transaction = dst_conn.begin()
            try:
                for table_name in TABLE_ORDER:
                    if table_name not in Base.metadata.tables or table_name not in source_metadata.tables:
                        continue
                    target_table = Base.metadata.tables[table_name]
                    source_table = source_metadata.tables[table_name]
                    column_names = [column.name for column in source_table.c if column.name in target_table.c]
                    if not column_names:
                        continue
                    inserted = skipped = conflicts = 0
                    rows = src_conn.execute(
                        select(*(source_table.c[name] for name in column_names))
                    ).mappings().all()
                    for row in rows:
                        payload = _coerce_payload(target_table, _row_payload(row))
                        existing = None
                        pk_clause = _pk_where(target_table, payload)
                        if pk_clause is not None:
                            existing_row = dst_conn.execute(select(target_table).where(pk_clause)).mappings().first()
                            existing = dict(existing_row) if existing_row else None
                        if existing is not None:
                            if _same_row(existing, payload, table_name):
                                skipped += 1
                            else:
                                conflicts += 1
                            continue
                        dst_conn.execute(target_table.insert().values(**payload))
                        inserted += 1
                    summary["tables"][table_name] = {
                        "read": len(rows),
                        "inserted": inserted,
                        "skipped": skipped,
                        "conflicts": conflicts,
                        "expected_post_count": summary["pre_counts"].get(table_name, 0) + inserted,
                    }

                summary["backfill"] = _backfill_article_sources_by_domain(dst_conn)

                for table_name in TABLE_ORDER:
                    summary["post_counts"][table_name] = _table_count(dst_conn, table_name)

                summary["relationship_checks"] = _relationship_checks(dst_conn)
                summary["blocking_failures"] = _blocking_failures(summary)
                summary["gate_passed"] = not any(summary["blocking_failures"].values())
                if summary["gate_passed"]:
                    for table_name in TABLE_ORDER:
                        _reset_pg_sequence(dst_conn, table_name)
                    transaction.commit()
                else:
                    transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
    finally:
        src_engine.dispose()
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migrate readonly SQLite data into configured database")
    parser.add_argument("--source", required=True, help="Path to source SQLite database")
    args = parser.parse_args(argv)
    summary = migrate_sqlite_to_database(args.source)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not summary["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
