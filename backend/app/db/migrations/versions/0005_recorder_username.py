"""Store the recorder account name alongside the password."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# 升级前只有一个记录者，补一个固定账号名，口令保持不变。
LEGACY_USERNAME = "admin"


def upgrade() -> None:
    op.add_column("recorder_account", sa.Column("username", sa.Text()))
    op.execute(
        sa.text("UPDATE recorder_account SET username = :name WHERE username IS NULL").bindparams(
            name=LEGACY_USERNAME
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("recorder_account") as batch:
        batch.drop_column("username")
