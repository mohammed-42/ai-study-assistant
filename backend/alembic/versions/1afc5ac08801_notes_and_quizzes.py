"""notes_and_quizzes

Revision ID: 1afc5ac08801
Revises: 159f277202ec
Create Date: 2026-10-18 11:23:59.848381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1afc5ac08801'
down_revision: Union[str, Sequence[str], None] = '159f277202ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('subject_id', sa.UUID(), nullable=True),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('note_type', sa.String(length=50), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notes_document_id'), 'notes', ['document_id'], unique=False)
    op.create_index(op.f('ix_notes_owner_id'), 'notes', ['owner_id'], unique=False)
    op.create_index(op.f('ix_notes_subject_id'), 'notes', ['subject_id'], unique=False)
    op.create_table('quizzes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('subject_id', sa.UUID(), nullable=True),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('quiz_type', sa.Enum('MCQ', 'SHORT_ANSWER', 'MIXED', name='quiztype'), nullable=False),
    sa.Column('difficulty', sa.Enum('EASY', 'MEDIUM', 'HARD', name='quizdifficulty'), nullable=False),
    sa.Column('question_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', name='quizstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['owner_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quizzes_document_id'), 'quizzes', ['document_id'], unique=False)
    op.create_index(op.f('ix_quizzes_owner_id'), 'quizzes', ['owner_id'], unique=False)
    op.create_index(op.f('ix_quizzes_subject_id'), 'quizzes', ['subject_id'], unique=False)
    op.create_table('quiz_attempts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('quiz_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('total_questions', sa.Integer(), nullable=False),
    sa.Column('correct_answers', sa.Integer(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_attempts_quiz_id'), 'quiz_attempts', ['quiz_id'], unique=False)
    op.create_index(op.f('ix_quiz_attempts_user_id'), 'quiz_attempts', ['user_id'], unique=False)
    op.create_table('quiz_questions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('quiz_id', sa.UUID(), nullable=False),
    sa.Column('question_text', sa.Text(), nullable=False),
    sa.Column('question_type', sa.String(length=20), nullable=False),
    sa.Column('options', sa.Text(), nullable=True),
    sa.Column('correct_option_index', sa.Integer(), nullable=True),
    sa.Column('model_answer', sa.Text(), nullable=True),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('page_start', sa.Integer(), nullable=True),
    sa.Column('page_end', sa.Integer(), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_questions_quiz_id'), 'quiz_questions', ['quiz_id'], unique=False)
    op.create_table('quiz_responses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('attempt_id', sa.UUID(), nullable=False),
    sa.Column('question_id', sa.UUID(), nullable=False),
    sa.Column('selected_option_index', sa.Integer(), nullable=True),
    sa.Column('user_answer', sa.Text(), nullable=True),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['quiz_attempts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_responses_attempt_id'), 'quiz_responses', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_quiz_responses_question_id'), 'quiz_responses', ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_quiz_responses_question_id'), table_name='quiz_responses')
    op.drop_index(op.f('ix_quiz_responses_attempt_id'), table_name='quiz_responses')
    op.drop_table('quiz_responses')
    op.drop_index(op.f('ix_quiz_questions_quiz_id'), table_name='quiz_questions')
    op.drop_table('quiz_questions')
    op.drop_index(op.f('ix_quiz_attempts_user_id'), table_name='quiz_attempts')
    op.drop_index(op.f('ix_quiz_attempts_quiz_id'), table_name='quiz_attempts')
    op.drop_table('quiz_attempts')
    op.drop_index(op.f('ix_quizzes_subject_id'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_owner_id'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_document_id'), table_name='quizzes')
    op.drop_table('quizzes')
    op.drop_index(op.f('ix_notes_subject_id'), table_name='notes')
    op.drop_index(op.f('ix_notes_owner_id'), table_name='notes')
    op.drop_index(op.f('ix_notes_document_id'), table_name='notes')
    op.drop_table('notes')
