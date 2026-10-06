"""Add project.proposal_id (unique) for proposal-to-project traceability

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-08-24 00:00:00.000000

UAT closure pass §1: the workflow doc requires a project to be traceable
back to the proposal/lead that produced it, and asks whether duplicate
project creation from the same accepted proposal is prevented or allowed.
No such link existed at all before this. The unique constraint on
proposal_id IS the answer/enforcement, not just a traceability field.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, None] = 'b2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()
    if not column_exists(bind, 'projects', 'proposal_id'):
        op.add_column('projects', sa.Column('proposal_id', sa.Uuid(), nullable=True))
        op.create_foreign_key('fk_projects_proposal_id', 'projects', 'proposals', ['proposal_id'], ['id'])
        op.create_unique_constraint('uq_projects_proposal_id', 'projects', ['proposal_id'])
        op.create_index('ix_projects_proposal_id', 'projects', ['proposal_id'])


def downgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, 'projects', 'proposal_id'):
        op.drop_index('ix_projects_proposal_id', table_name='projects')
        op.drop_constraint('uq_projects_proposal_id', 'projects', type_='unique')
        op.drop_constraint('fk_projects_proposal_id', 'projects', type_='foreignkey')
        op.drop_column('projects', 'proposal_id')
