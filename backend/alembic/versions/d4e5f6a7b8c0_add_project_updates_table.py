"""Add project_updates table (daily project updates)

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-08-24 00:00:00.000000

UAT closure pass §2: the workflow doc's "Daily Project Updates" (§8) and
Employee-View-vs-Client-View split (§16) had no backing entity at all —
only Task status and a single manually-set Project.progress_percent
existed. This is the missing piece: employee-authored, dated updates,
individually flaggable by a PM/admin as client-visible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c0'
down_revision: Union[str, None] = 'c3d4e5f6a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, 'project_updates'):
        op.create_table(
            'project_updates',
            sa.Column('project_id', sa.Uuid(), nullable=False),
            sa.Column('employee_id', sa.Uuid(), nullable=False),
            sa.Column('update_text', sa.Text(), nullable=False),
            sa.Column('hours_logged', sa.Numeric(5, 2), nullable=True),
            sa.Column('client_visible', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_project_updates_project_id', 'project_updates', ['project_id'])
        op.create_index('ix_project_updates_employee_id', 'project_updates', ['employee_id'])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, 'project_updates'):
        op.drop_index('ix_project_updates_employee_id', table_name='project_updates')
        op.drop_index('ix_project_updates_project_id', table_name='project_updates')
        op.drop_table('project_updates')
