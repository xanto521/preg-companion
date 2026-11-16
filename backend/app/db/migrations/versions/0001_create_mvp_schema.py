"""Create MVP schema."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'attachment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_type', sa.Text(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=True),
        sa.Column('mime', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.Text(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('attachment', schema=None) as batch_op:
        batch_op.create_index('ix_attachment_owner', ['owner_type', 'owner_id'], unique=False)

    op.create_table(
        'daily_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('mood', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('viewer_visible', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('log_date'),
    )
    op.create_table(
        'metric_def',
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('unit', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('value_type', sa.Text(), nullable=False),
        sa.Column('ref_low', sa.Float(), nullable=True),
        sa.Column('ref_high', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'milestone_rule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('start_ga_days', sa.Integer(), nullable=False),
        sa.Column('end_ga_days', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('start_ga_days <= end_ga_days', name='ck_milestone_window'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_table(
        'note',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(none_as_null=True), nullable=True),
        sa.Column('viewer_visible', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'pregnancy',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edd_date', sa.Date(), nullable=False),
        sa.Column('edd_source', sa.Text(), nullable=False),
        sa.Column('lmp_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'share_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_table(
        'supplement_plan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('dosage', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('remind_time', sa.Time(), nullable=True),
        sa.Column('rrule', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('viewer_visible', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'checkup',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pregnancy_id', sa.Integer(), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('visit_time', sa.Time(), nullable=True),
        sa.Column('hospital', sa.Text(), nullable=True),
        sa.Column('doctor', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('advice', sa.Text(), nullable=True),
        sa.Column('next_visit_date', sa.Date(), nullable=True),
        sa.Column('next_visit_time', sa.Time(), nullable=True),
        sa.Column('viewer_visible', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('viewer_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pregnancy_id'], ['pregnancy.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('checkup', schema=None) as batch_op:
        batch_op.create_index('ix_checkup_visit_date', ['visit_date'], unique=False)

    op.create_table(
        'edd_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pregnancy_id', sa.Integer(), nullable=False),
        sa.Column('edd_date', sa.Date(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pregnancy_id'], ['pregnancy.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'meal_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('daily_log_id', sa.Integer(), nullable=False),
        sa.Column('meal_type', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('attachment_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachment.id']),
        sa.ForeignKeyConstraint(['daily_log_id'], ['daily_log.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'supplement_check',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('check_date', sa.Date(), nullable=False),
        sa.Column('taken', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['supplement_plan.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'check_date', name='uq_supplement_check_plan_date'),
    )
    op.create_table(
        'symptom_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('daily_log_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.Text(), nullable=False),
        sa.Column('severity', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['daily_log_id'], ['daily_log.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'metric_value',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('checkup_id', sa.Integer(), nullable=True),
        sa.Column('daily_log_id', sa.Integer(), nullable=True),
        sa.Column('measured_at', sa.DateTime(), nullable=False),
        sa.Column('ga_days', sa.Integer(), nullable=True),
        sa.Column('value_num', sa.Float(), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['checkup_id'], ['checkup.id']),
        sa.ForeignKeyConstraint(['code'], ['metric_def.code']),
        sa.ForeignKeyConstraint(['daily_log_id'], ['daily_log.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('metric_value', schema=None) as batch_op:
        batch_op.create_index('ix_metric_value_code_measured_at', ['code', 'measured_at'], unique=False)

    op.create_table(
        'question',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('checkup_id', sa.Integer(), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['checkup_id'], ['checkup.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('question')
    with op.batch_alter_table('metric_value', schema=None) as batch_op:
        batch_op.drop_index('ix_metric_value_code_measured_at')

    op.drop_table('metric_value')
    op.drop_table('symptom_entry')
    op.drop_table('supplement_check')
    op.drop_table('meal_entry')
    op.drop_table('edd_history')
    with op.batch_alter_table('checkup', schema=None) as batch_op:
        batch_op.drop_index('ix_checkup_visit_date')

    op.drop_table('checkup')
    op.drop_table('supplement_plan')
    op.drop_table('share_token')
    op.drop_table('pregnancy')
    op.drop_table('note')
    op.drop_table('milestone_rule')
    op.drop_table('metric_def')
    op.drop_table('daily_log')
    with op.batch_alter_table('attachment', schema=None) as batch_op:
        batch_op.drop_index('ix_attachment_owner')

    op.drop_table('attachment')
