"""study_plans_and_tasks

Revision ID: e34c954767af
Revises: 1afc5ac08801
Create Date: 2026-10-18 12:44:53.050895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e34c954767af'
down_revision: Union[str, Sequence[str], None] = '1afc5ac08801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('study_plans',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('subject_id', sa.UUID(), nullable=True),
    sa.Column('exam_date', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('daily_minutes', sa.Integer(), nullable=False),
    sa.Column('preferred_days', sa.String(length=50), nullable=False),
    sa.Column('topics', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_study_plans_owner_id'), 'study_plans', ['owner_id'], unique=False)
    op.create_index(op.f('ix_study_plans_subject_id'), 'study_plans', ['subject_id'], unique=False)
    op.create_table('study_tasks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('topic', sa.String(length=500), nullable=False),
    sa.Column('importance', sa.Integer(), nullable=False),
    sa.Column('scheduled_days', sa.String(length=50), nullable=False),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('estimated_minutes', sa.Integer(), nullable=False),
    sa.Column('actual_minutes', sa.Integer(), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['plan_id'], ['study_plans.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_study_tasks_plan_id'), 'study_tasks', ['plan_id'], unique=False)
    op.create_index(op.f('ix_study_tasks_scheduled_date'), 'study_tasks', ['scheduled_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_study_tasks_scheduled_date'), table_name='study_tasks')
    op.drop_index(op.f('ix_study_tasks_plan_id'), table_name='study_tasks')
    op.drop_table('study_tasks')
    op.drop_index(op.f('ix_study_plans_subject_id'), table_name='study_plans')
    op.drop_index(op.f('ix_study_plans_owner_id'), table_name='study_plans')
    op.drop_table('study_plans')
