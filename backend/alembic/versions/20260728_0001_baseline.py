"""Baseline the pre-queue PowerAI Hot schema."""
from alembic import op

from models import schema  # noqa: F401
from models.database import Base

revision = "20260728_0001"
down_revision = None
branch_labels = None
depends_on = None

_POST_BASELINE_TABLES = {"persistent_jobs", "alert_states"}


def upgrade() -> None:
    bind = op.get_bind()
    for table in Base.metadata.sorted_tables:
        if table.name not in _POST_BASELINE_TABLES:
            table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in _POST_BASELINE_TABLES:
            table.drop(bind, checkfirst=True)
