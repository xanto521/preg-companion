"""Move scheduled visits into independent appointment records."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("time", sa.Time()),
        sa.Column("hospital", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("viewer_visible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("ix_appointment_day", "appointment", ["day"])
    # Keep IDs and versions so subscribed calendars retain their event identity.
    op.execute("""
        INSERT INTO appointment (id, day, time, hospital, viewer_visible, version, updated_at, deleted_at)
        SELECT id, next_visit_date, next_visit_time, COALESCE(NULLIF(next_visit_hospital, ''), hospital),
               viewer_visible, version, updated_at, deleted_at
        FROM checkup WHERE next_visit_date IS NOT NULL
    """)
    for column in ("next_visit_date", "next_visit_time", "next_visit_hospital"):
        op.drop_column("checkup", column)


def downgrade() -> None:
    raise RuntimeError("Independent appointments cannot be represented in revision 0003. Restore a pre-upgrade backup.")
