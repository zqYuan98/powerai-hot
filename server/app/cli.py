"""运维命令行：不经过队列、直接执行，便于排障与首次试跑。

python -m app.cli seed                      # 同步信源注册表与默认订阅
python -m app.cli collect <key|all>         # 立即采集（并处理新条目）
python -m app.cli process                   # 处理所有待处理/可重试条目
python -m app.cli digest daily [YYYY-MM-DD] # 生成日报（weekly 传周一日期）
python -m app.cli heat                      # 重算热度
python -m app.cli backup                    # 立即备份数据库（pg_dump）
python -m app.cli reindex                   # 补算向量并重建事件归并（首次配置 Embedding 后执行）
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.collectors.http import PoliteClient
from app.config import settings
from app.db import SessionLocal, engine
from app.digest.builder import build_digest
from app.logs import setup_logging
from app.models import Item, Source
from app.models.enums import DigestKind, ItemStatus
from app.pipeline.collect import collect_source
from app.pipeline.process import MAX_ATTEMPTS, process_items
from app.pipeline.reindex import backfill_embeddings, rebuild_stories
from app.pipeline.stories import recompute_heat
from app.seed.loader import seed_watch_rules, sync_sources
from app.worker.jobs import backup_job


async def _process(client: PoliteClient, ids: list[int]) -> None:
    for start in range(0, len(ids), 15):
        async with SessionLocal() as session:
            stats = await process_items(session, client, ids[start:start + 15])
        errors = f"，错误 {stats.errors[:2]}" if stats.errors else ""
        print(f"  处理 {stats.total}：精读 {stats.analyzed}，精选 {stats.selected}，淘汰 {stats.screened_out}，"
              f"失败 {stats.failed}，回捞正文 {stats.fulltext}{errors}")


async def run(args: argparse.Namespace) -> None:
    async with PoliteClient() as client:
        if args.cmd == "seed":
            async with SessionLocal() as session:
                n = await sync_sources(session)
                await seed_watch_rules(session)
            print(f"已同步 {n} 个信源")
        elif args.cmd == "collect":
            async with SessionLocal() as session:
                stmt = select(Source) if args.key == "all" else select(Source).where(Source.key == args.key)
                if args.key == "all":
                    stmt = stmt.where(Source.enabled)
                sources = (await session.scalars(stmt)).all()
                if not sources:
                    raise SystemExit(f"找不到信源 {args.key}")
                for source in sources:
                    out = await collect_source(session, client, source)
                    status = "正常" if out.healthy else "失败"
                    print(f"[{source.key}] {status} 抓到 {out.fetched} 条，新增 {len(out.new_ids)}"
                          + (f"，{out.error}" if out.error else ""))
                    if out.new_ids and not args.no_process:
                        await _process(client, out.new_ids)
        elif args.cmd == "process":
            async with SessionLocal() as session:
                ids = list((await session.scalars(select(Item.id).where(
                    Item.status.in_((ItemStatus.NEW, ItemStatus.FAILED)), Item.attempts < MAX_ATTEMPTS
                ).order_by(Item.id).limit(args.limit))).all())
            print(f"待处理 {len(ids)} 条")
            await _process(client, ids)
        elif args.cmd == "digest":
            kind = DigestKind(args.kind)
            today = datetime.now(settings.tz).date()
            default = today if kind == DigestKind.DAILY else today - timedelta(days=today.weekday())
            async with SessionLocal() as session:
                d = await build_digest(session, kind, date.fromisoformat(args.date) if args.date else default)
            print(d.markdown)
        elif args.cmd == "heat":
            async with SessionLocal() as session:
                print(f"更新 {await recompute_heat(session)} 个事件")
        elif args.cmd == "reindex":
            async with SessionLocal() as session:
                print(f"补算向量 {await backfill_embeddings(session)} 条")
                total, multi = await rebuild_stories(session)
                print(f"重建事件 {total} 个，其中多来源 {multi} 个")
        elif args.cmd == "backup":
            async with SessionLocal() as session:
                print(await backup_job(session, client, {}))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    c = sub.add_parser("collect")
    c.add_argument("key")
    c.add_argument("--no-process", action="store_true")
    pr = sub.add_parser("process")
    pr.add_argument("--limit", type=int, default=None, help="最多处理多少条")
    d = sub.add_parser("digest")
    d.add_argument("kind", choices=["daily", "weekly"])
    d.add_argument("date", nargs="?")
    sub.add_parser("heat")
    sub.add_parser("backup")
    sub.add_parser("reindex")
    setup_logging()
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
