"""Backup retention helper.

The shell script runs pg_dump. This module only reports configured retention
state and deletes backup files older than the retention window when requested.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply backup retention")
    parser.add_argument("--dir", default="/opt/e-ai/backups")
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.keep_days)
    removed: list[str] = []
    files = sorted(root.glob("*.dump*")) + sorted(root.glob("*.sql*"))
    if args.prune:
        for path in files:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                path.unlink()
                removed.append(path.name)
    print(json.dumps({
        "backup_dir": str(root),
        "keep_days": args.keep_days,
        "files": [p.name for p in files if p.exists()],
        "removed": removed,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
