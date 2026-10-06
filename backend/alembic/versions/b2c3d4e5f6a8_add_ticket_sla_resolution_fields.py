"""Add ticket SLA due date and resolution/closed tracking fields

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-24 00:00:00.000000

Workflow doc "Complete Website & Portal Workflow" §12: "The system should
track SLA/response and resolution deadlines based on priority" plus
"Resolution"/"Closed date" ticket fields — none of this existed before
(only a `priority` enum column). See app/utils/sla.py for the deadline
computation and app/routers/ticket.py's update_ticket for the auto-stamp.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()
    for col_name, col_type in [
        ('sla_due_at', sa.DateTime(timezone=True)),
        ('resolution', sa.Text()),
        ('resolved_at', sa.DateTime(timezone=True)),
        ('closed_at', sa.DateTime(timezone=True)),
    ]:
        if not column_exists(bind, 'tickets', col_name):
            op.add_column('tickets', sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for col_name in ('closed_at', 'resolved_at', 'resolution', 'sla_due_at'):
        if column_exists(bind, 'tickets', col_name):
            op.drop_column('tickets', col_name)
