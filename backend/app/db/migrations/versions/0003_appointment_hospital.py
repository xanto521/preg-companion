"""Store an optional hospital override for the next appointment."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checkup", sa.Column("next_visit_hospital", sa.Text()))


def downgrade() -> None:
    op.drop_column("checkup", "next_visit_hospital")
