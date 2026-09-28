"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-28

冻结的 DDL：不引用运行时 metadata，保证迁移可复现。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    # 仅供测试环境（pgserver 不带 contrib）：alembic -x skip_trgm=1 upgrade head
    skip_trgm = context.get_x_argument(as_dictionary=True).get("skip_trgm") == "1"
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if not skip_trgm:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("tier", sa.String(8), nullable=False, server_default="T2"),
        sa.Column("category", sa.String(16), nullable=False, server_default="industry"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("interval_min", sa.Integer, nullable=False, server_default="120"),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text),
        sa.Column("last_run_at", TS),
        sa.Column("last_ok_at", TS),
        sa.Column("last_error", sa.Text),
        sa.Column("fail_streak", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )

    op.create_table(
        "source_runs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", TS, nullable=False, server_default=NOW),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("transport_status", sa.String(16), nullable=False),
        sa.Column("parse_status", sa.String(16), nullable=False),
        sa.Column("http_status", sa.SmallInteger),
        sa.Column("fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
    )
    op.create_index("ix_source_runs_source_started", "source_runs", ["source_id", sa.text("started_at DESC")])

    op.create_table(
        "stories",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("digest", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("first_seen_at", TS, nullable=False, server_default=NOW),
        sa.Column("last_seen_at", TS, nullable=False, server_default=NOW),
        sa.Column("item_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("heat", sa.Float, nullable=False, server_default="0"),
        sa.Column("digest_item_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_stories_heat", "stories", [sa.text("heat DESC")])

    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(8), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("external_id", sa.String(200)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("title_zh", sa.Text),
        sa.Column("content_text", sa.Text),
        sa.Column("content_html", sa.Text),
        sa.Column("published_at", TS),
        sa.Column("first_seen_at", TS, nullable=False, server_default=NOW),
        sa.Column("last_seen_at", TS, nullable=False, server_default=NOW),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("status_reason", sa.Text),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("analyzed_at", TS),
        sa.Column("channel", sa.String(16), nullable=False, server_default="industry"),
        sa.Column("province", sa.String(16)),
        sa.Column("summary", sa.Text),
        sa.Column("reason", sa.Text),
        sa.Column("action", sa.Text),
        sa.Column("tags", ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("event_key", sa.String(200)),
        sa.Column("d_relevance", sa.SmallInteger),
        sa.Column("d_opportunity", sa.SmallInteger),
        sa.Column("d_certainty", sa.SmallInteger),
        sa.Column("d_timeliness", sa.SmallInteger),
        sa.Column("d_impact", sa.SmallInteger),
        sa.Column("score", sa.Float),
        sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("story_id", sa.BigInteger, sa.ForeignKey("stories.id", ondelete="SET NULL")),
        sa.Column("is_story_lead", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("embedding", Vector(1024)),
        sa.Column("starred_at", TS),
        sa.Column("read_at", TS),
        sa.Column("note", sa.Text),
    )
    feed_where = sa.text("status = 'analyzed' AND is_story_lead")
    op.create_index("ix_items_feed", "items", [sa.text("first_seen_at DESC"), sa.text("id DESC")],
                    postgresql_where=feed_where)
    op.create_index("ix_items_feed_selected", "items", [sa.text("first_seen_at DESC"), sa.text("id DESC")],
                    postgresql_where=sa.text("selected AND is_story_lead"))
    op.create_index("ix_items_channel_feed", "items",
                    ["channel", sa.text("first_seen_at DESC"), sa.text("id DESC")], postgresql_where=feed_where)
    op.create_index("ix_items_status", "items", ["status"])
    op.create_index("ix_items_story", "items", ["story_id"])
    op.create_index("ix_items_source", "items", ["source_id"])
    op.create_index(
        "ix_items_starred", "items", ["starred_at"], postgresql_where=sa.text("starred_at IS NOT NULL")
    )
    if not skip_trgm:
        op.execute(
            "CREATE INDEX ix_items_title_trgm ON items "
            "USING gin ((coalesce(title_zh, '') || ' ' || title) gin_trgm_ops)"
        )
    op.execute("CREATE INDEX ix_items_embedding ON items USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "leads",
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("project_name", sa.Text),
        sa.Column("owner", sa.Text),
        sa.Column("province", sa.String(16)),
        sa.Column("voltage_kv", sa.Integer),
        sa.Column("amount_wan", sa.Numeric(14, 2)),
        sa.Column("stage", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("bid_no", sa.String(100)),
        sa.Column("deadline_at", TS),
        sa.Column("qualification", sa.Text),
        sa.Column("winner", sa.Text),
        sa.Column("biz_line", sa.String(16), nullable=False, server_default="other"),
        sa.Column("match_score", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("dropped_fields", ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("follow_status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("follow_note", sa.Text),
        sa.Column("remind_at", TS),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("ix_leads_deadline", "leads", ["deadline_at"])
    op.create_index("ix_leads_follow", "leads", ["follow_status"])
    op.create_index("ix_leads_bid_no", "leads", ["bid_no"])

    op.create_table(
        "watch_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("keywords", ARRAY(sa.String(64)), nullable=False, server_default="{}"),
        sa.Column("provinces", ARRAY(sa.String(16)), nullable=False, server_default="{}"),
        sa.Column("channels", ARRAY(sa.String(16)), nullable=False, server_default="{}"),
        sa.Column("min_amount_wan", sa.Numeric(14, 2)),
        sa.Column("min_voltage_kv", sa.Integer),
        sa.Column("notify", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("watch_rules.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text),
        sa.Column("sent_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("item_id", "rule_id", "kind", postgresql_nulls_not_distinct=True),
    )

    op.create_table(
        "digests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("issue_no", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False, server_default="{}"),
        sa.Column("markdown", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("kind", "period_start"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("dedupe_key", sa.String(200)),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("run_after", TS, nullable=False, server_default=NOW),
        sa.Column("locked_by", sa.String(64)),
        sa.Column("heartbeat_at", TS),
        sa.Column("error", sa.Text),
        sa.Column("result", JSONB),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("finished_at", TS),
    )
    op.create_index(
        "ix_jobs_claim", "jobs", ["status", "priority", "run_after"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ux_jobs_active_dedupe", "jobs", ["dedupe_key"], unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("task", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_yuan", sa.Float, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("ix_llm_calls_created", "llm_calls", [sa.text("created_at DESC")])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", JSONB),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
    )


def downgrade() -> None:
    for table in (
        "app_settings", "llm_calls", "jobs", "digests", "notifications", "watch_rules",
        "leads", "items", "stories", "source_runs", "sources",
    ):
        op.drop_table(table)
