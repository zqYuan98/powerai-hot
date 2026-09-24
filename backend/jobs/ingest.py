"""Standalone ingest CLI for systemd timers."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from models.database import SessionLocal, init_db
from services.ingest import ingest_once


def _window_key(group: str, value: str | None) -> str:
    if value:
        return value
    now = datetime.now(timezone.utc)
    if group == "papers":
        window = now.strftime("%Y-%m-%d")
    else:
        hour = (now.hour // 2) * 2
        window = now.replace(hour=hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%MZ")
    return f"ingest-{group}:{window}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run E-AI ingest outside the web process")
    parser.add_argument("--group", choices=["news", "papers", "all"], default="news")
    parser.add_argument("--run-key", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-total", type=int, default=40)
    args = parser.parse_args(argv)

    init_db()
    db = SessionLocal()
    try:
        stats = ingest_once(
            db,
            group=args.group,
            limit=args.limit,
            max_total=args.max_total,
            run_key=_window_key(args.group, args.run_key),
        )
        print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    finally:
        db.close()


if __name__ == "__main__":
    main()
