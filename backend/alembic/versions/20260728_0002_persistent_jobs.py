"""Add durable jobs and persistent alert state."""
from alembic import op

from models import schema

revision = "20260728_0002"
down_revision = "20260728_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    schema.PersistentJob.__table__.create(bind, checkfirst=True)
    schema.AlertState.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    schema.AlertState.__table__.drop(bind, checkfirst=True)
    schema.PersistentJob.__table__.drop(bind, checkfirst=True)
