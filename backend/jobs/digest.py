"""Standalone digest CLI."""
from __future__ import annotations

import json

from models.database import SessionLocal, init_db
from services.digest import build_daily_digest


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        report = build_daily_digest(db)
        print(json.dumps({"id": report.id, "title": report.title, "status": report.status}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
