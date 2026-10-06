"""Add proposal client_comment and rejection_reason columns

Revision ID: a1b2c3d4e5f7
Revises: f3a4b5c6d7e8
Create Date: 2026-08-24 00:00:00.000000

Workflow doc "Complete Website & Portal Workflow" §7 lists "Client
comments" and "Rejection reason" as required proposal-history fields.
Populated by the new client-facing accept/reject endpoints
(app/routers/clients.py's /clients/me/proposals/{id}/accept|reject).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()
    if not column_exists(bind, 'proposals', 'client_comment'):
        op.add_column('proposals', sa.Column('client_comment', sa.Text(), nullable=True))
    if not column_exists(bind, 'proposals', 'rejection_reason'):
        op.add_column('proposals', sa.Column('rejection_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, 'proposals', 'rejection_reason'):
        op.drop_column('proposals', 'rejection_reason')
    if column_exists(bind, 'proposals', 'client_comment'):
        op.drop_column('proposals', 'client_comment')
