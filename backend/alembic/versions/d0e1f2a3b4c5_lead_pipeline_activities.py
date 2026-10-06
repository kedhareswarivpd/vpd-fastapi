"""Add lead_status.proposal_created and the lead_activities timeline table

Revision ID: d0e1f2a3b4c5
Revises: c9d1e2f3a4b5
Create Date: 2026-08-24 00:00:00.000000

Backs the one-way Lead pipeline (new -> contacted -> requirement_gathering
-> proposal_created -> proposal_sent -> proposal_approved -> converted, with
disqualified as a terminal branch) — see app/services/lead_pipeline.py.
`proposal_created` marks a drafted-but-not-yet-emailed proposal, distinct
from `proposal_sent`. lead_activities is the step-wise evidence log (call
logged, requirement gathering, proposal created/sent/approved, disqualified,
converted) shown on the lead flow page.

`ALTER TYPE ... ADD VALUE` needs its own autocommit block — same reasoning
as 7130a92059c9_partner_portal.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'proposal_created'")

    op.create_table(
        'lead_activities',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('lead_id', sa.Uuid(), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_lead_activities_lead_id', 'lead_activities', ['lead_id'])


def downgrade() -> None:
    op.drop_index('ix_lead_activities_lead_id', table_name='lead_activities')
    op.drop_table('lead_activities')
    # Postgres does not support dropping enum values — the proposal_created
    # addition is left in place on downgrade.
