"""feedback

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29

公开上线：访客反馈表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("contact", sa.String(200)),
        sa.Column("page_url", sa.Text),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("status", sa.String(8), nullable=False, server_default="new"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("ix_feedback_created", "feedback", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("feedback")
