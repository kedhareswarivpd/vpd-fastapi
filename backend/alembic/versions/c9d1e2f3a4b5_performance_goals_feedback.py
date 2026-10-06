"""Add performance_goals, performance_feedback tables and
performance_reviews.acknowledged_at

Revision ID: c9d1e2f3a4b5
Revises: b8c9d1e2f3a4
Create Date: 2026-08-24 00:00:00.000000

Performance goals/feedback lifecycle: previously only a free-text
PerformanceReview.goals blob existed, no individually trackable goals,
no continuous feedback, no review-acknowledgment field — and no
admin-side create/list/update endpoints for reviews at all (only
GET /employees/me/performance-reviews existed).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9d1e2f3a4b5'
down_revision: Union[str, None] = 'b8c9d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c['name'] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, 'performance_reviews', 'acknowledged_at'):
        op.add_column('performance_reviews', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))

    if not table_exists(bind, 'performance_goals'):
        op.create_table(
            'performance_goals',
            sa.Column('employee_id', sa.Uuid(), nullable=False),
            sa.Column('review_id', sa.Uuid(), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_date', sa.Date(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='not_started'),
            sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_by', sa.Uuid(), nullable=True),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
            sa.ForeignKeyConstraint(['review_id'], ['performance_reviews.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_performance_goals_employee_id', 'performance_goals', ['employee_id'])
        op.create_index('ix_performance_goals_review_id', 'performance_goals', ['review_id'])

    if not table_exists(bind, 'performance_feedback'):
        op.create_table(
            'performance_feedback',
            sa.Column('employee_id', sa.Uuid(), nullable=False),
            sa.Column('given_by', sa.Uuid(), nullable=False),
            sa.Column('feedback_text', sa.Text(), nullable=False),
            sa.Column('feedback_type', sa.String(length=20), nullable=False, server_default='general'),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
            sa.ForeignKeyConstraint(['given_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_performance_feedback_employee_id', 'performance_feedback', ['employee_id'])
        op.create_index('ix_performance_feedback_given_by', 'performance_feedback', ['given_by'])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, 'performance_feedback'):
        op.drop_index('ix_performance_feedback_given_by', table_name='performance_feedback')
        op.drop_index('ix_performance_feedback_employee_id', table_name='performance_feedback')
        op.drop_table('performance_feedback')
    if table_exists(bind, 'performance_goals'):
        op.drop_index('ix_performance_goals_review_id', table_name='performance_goals')
        op.drop_index('ix_performance_goals_employee_id', table_name='performance_goals')
        op.drop_table('performance_goals')
    if column_exists(bind, 'performance_reviews', 'acknowledged_at'):
        op.drop_column('performance_reviews', 'acknowledged_at')
