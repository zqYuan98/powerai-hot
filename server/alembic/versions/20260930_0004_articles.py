"""articles

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30

知识库：公众号与专业网站的行业知识文章。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("account", sa.String(128)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content_text", sa.Text),
        sa.Column("published_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("status_reason", sa.Text),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("analyzed_at", TS),
        sa.Column("duplicate_of", sa.BigInteger, sa.ForeignKey("articles.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text),
        sa.Column("title_zh", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("key_points", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("scenarios", sa.Text),
        sa.Column("solution_use", sa.Text),
        sa.Column("standards", ARRAY(sa.String(64)), nullable=False, server_default="{}"),
        sa.Column("domain", sa.String(16), nullable=False, server_default="general"),
        sa.Column("ktype", sa.String(16), nullable=False, server_default="principle"),
        sa.Column("tags", ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("d_depth", sa.SmallInteger),
        sa.Column("d_practical", sa.SmallInteger),
        sa.Column("d_accuracy", sa.SmallInteger),
        sa.Column("d_original", sa.SmallInteger),
        sa.Column("score", sa.Float),
        sa.Column("embedding", Vector(1024)),
    )
    op.create_index("ix_articles_visible", "articles", ["status", sa.text("score DESC")])
    op.create_index("ix_articles_created", "articles", [sa.text("created_at DESC")])
    op.execute("CREATE INDEX ix_articles_embedding ON articles USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("articles")
