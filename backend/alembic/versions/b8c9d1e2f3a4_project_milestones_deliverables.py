"""Add project_milestones and project_deliverables tables

Revision ID: b8c9d1e2f3a4
Revises: a7b8c9d1e2f3
Create Date: 2026-08-24 00:00:00.000000

Project Tracker (workflow doc): milestones and deliverables previously
had no backing entity at all — a flat `Project.progress_percent` integer
and a `Project.deliverables` array of URL strings, no status/dates/
approval history for either.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8c9d1e2f3a4'
down_revision: Union[str, None] = 'a7b8c9d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, 'project_milestones'):
        op.create_table(
            'project_milestones',
            sa.Column('project_id', sa.Uuid(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('completed_date', sa.Date(), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
            sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('client_visible', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_project_milestones_project_id', 'project_milestones', ['project_id'])

    if not table_exists(bind, 'project_deliverables'):
        op.create_table(
            'project_deliverables',
            sa.Column('project_id', sa.Uuid(), nullable=False),
            sa.Column('milestone_id', sa.Uuid(), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('file_url', sa.String(length=500), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('client_comment', sa.Text(), nullable=True),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['milestone_id'], ['project_milestones.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_project_deliverables_project_id', 'project_deliverables', ['project_id'])
        op.create_index('ix_project_deliverables_milestone_id', 'project_deliverables', ['milestone_id'])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, 'project_deliverables'):
        op.drop_index('ix_project_deliverables_milestone_id', table_name='project_deliverables')
        op.drop_index('ix_project_deliverables_project_id', table_name='project_deliverables')
        op.drop_table('project_deliverables')
    if table_exists(bind, 'project_milestones'):
        op.drop_index('ix_project_milestones_project_id', table_name='project_milestones')
        op.drop_table('project_milestones')
