"""Persist recorder access and gestational age at the visit."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Snapshot of the initial metric definitions. Existing codes keep their settings.
METRICS = (
    ("weight", "体重", "kg", "vital"),
    ("systolic_bp", "收缩压", "mmHg", "vital"),
    ("diastolic_bp", "舒张压", "mmHg", "vital"),
    ("fundal_height", "宫高", "cm", "vital"),
    ("abdominal_circumference", "腹围", "cm", "vital"),
    ("fetal_heart_rate", "胎心", "次/分", "vital"),
    ("bpd", "双顶径", "mm", "ultrasound"),
    ("femur_length", "股骨长", "mm", "ultrasound"),
)


def upgrade() -> None:
    op.create_table(
        "recorder_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.Text()),
        sa.Column("setup_hash", sa.Text()),
        sa.Column("setup_expires_at", sa.DateTime()),
        sa.CheckConstraint("id = 1", name="ck_recorder_account_singleton"),
    )
    op.create_table(
        "recorder_session",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.add_column("checkup", sa.Column("ga_days", sa.Integer()))
    op.create_index("ix_attachment_sha256", "attachment", ["sha256"])
    seed = sa.text(
        "INSERT INTO metric_def (code, name, unit, category, value_type) "
        "VALUES (:code, :name, :unit, :category, 'num') ON CONFLICT (code) DO NOTHING"
    )
    for code, name, unit, category in METRICS:
        op.execute(seed.bindparams(code=code, name=name, unit=unit, category=category))


def downgrade() -> None:
    op.drop_index("ix_attachment_sha256", table_name="attachment")
    # SQLite supports DROP COLUMN directly. Avoid rebuilding a table referenced by foreign keys.
    op.execute("ALTER TABLE checkup DROP COLUMN ga_days")
    op.drop_table("recorder_session")
    op.drop_table("recorder_account")
    # Retain metric definitions that records may already reference.
