"""gold labels and eval runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

精选校准：人工标注表与评测记录表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "gold_labels",
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("decision", sa.String(8), nullable=False),
        sa.Column("split", sa.String(12), nullable=False),
        sa.Column("stratum", sa.String(12), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("labeled_at", TS, nullable=False, server_default=NOW),
    )
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("split", sa.String(12), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="running"),
        sa.Column("error", sa.Text),
        sa.Column("params", JSONB, nullable=False, server_default="{}"),
        sa.Column("metrics", JSONB, nullable=False, server_default="{}"),
        sa.Column("sweep", JSONB, nullable=False, server_default="[]"),
        sa.Column("cases", JSONB, nullable=False, server_default="[]"),
        sa.Column("cost_yuan", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("finished_at", TS),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("gold_labels")
