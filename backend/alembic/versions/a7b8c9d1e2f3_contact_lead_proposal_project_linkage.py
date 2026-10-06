"""Contact->Lead auto-creation, Service/Industry linkage, proposal PM-review
stage, and project final-delivery-approval fields

Revision ID: a7b8c9d1e2f3
Revises: f6a7b8c9d1e2
Create Date: 2026-08-24 00:00:00.000000

Workflow-alignment pass: closes the gaps between the workflow doc's
end-to-end diagram (Contact -> Lead -> Proposal -> Project -> Client
Approval) and what previously existed as separate, only manually-connected
modules. See app/routers/contact.py (Lead auto-creation),
app/services/project_provisioning.py (Project auto-creation on proposal
acceptance), app/routers/proposals.py (submit-for-review/review), and the
Project final-delivery-approval fields.

`ALTER TYPE ... ADD VALUE` needs its own autocommit block — same reasoning
as 7130a92059c9_partner_portal.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7b8c9d1e2f3'
down_revision: Union[str, None] = 'f6a7b8c9d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c['name'] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE proposal_status ADD VALUE IF NOT EXISTS 'submitted_for_review'")
        op.execute("ALTER TYPE proposal_status ADD VALUE IF NOT EXISTS 'pm_approved'")
        op.execute("ALTER TYPE proposal_status ADD VALUE IF NOT EXISTS 'pm_rejected'")
        op.execute("ALTER TYPE proposal_status ADD VALUE IF NOT EXISTS 'superseded'")

    contact_cols = [
        ('service_id', sa.Uuid()), ('industry_id', sa.Uuid()),
        ('expected_budget', sa.Numeric(12, 2)), ('requirements', sa.Text()),
        ('lead_id', sa.Uuid()),
    ]
    for name, col_type in contact_cols:
        if not column_exists(bind, 'contact_submissions', name):
            op.add_column('contact_submissions', sa.Column(name, col_type, nullable=True))
    op.create_foreign_key('contact_submissions_service_id_fkey', 'contact_submissions', 'services', ['service_id'], ['id'])
    op.create_foreign_key('contact_submissions_industry_id_fkey', 'contact_submissions', 'industries', ['industry_id'], ['id'])
    op.create_foreign_key('contact_submissions_lead_id_fkey', 'contact_submissions', 'leads', ['lead_id'], ['id'])
    op.create_index('ix_contact_submissions_service_id', 'contact_submissions', ['service_id'])
    op.create_index('ix_contact_submissions_industry_id', 'contact_submissions', ['industry_id'])
    op.create_index('ix_contact_submissions_lead_id', 'contact_submissions', ['lead_id'])

    lead_cols = [
        ('service_id', sa.Uuid()), ('industry_id', sa.Uuid()),
        ('evaluation_date', sa.Date()), ('meeting_notes', sa.Text()),
        ('requirements_confirmed', sa.Boolean()), ('delivery_timeline', sa.String(200)),
        ('evaluation_result', sa.String(30)), ('rejection_reason', sa.Text()),
    ]
    for name, col_type in lead_cols:
        if not column_exists(bind, 'leads', name):
            default = sa.false() if name == 'requirements_confirmed' else None
            op.add_column('leads', sa.Column(name, col_type, nullable=True, server_default=default))
    op.create_foreign_key('leads_service_id_fkey', 'leads', 'services', ['service_id'], ['id'])
    op.create_foreign_key('leads_industry_id_fkey', 'leads', 'industries', ['industry_id'], ['id'])
    op.create_index('ix_leads_service_id', 'leads', ['service_id'])
    op.create_index('ix_leads_industry_id', 'leads', ['industry_id'])

    proposal_cols = [('service_id', sa.Uuid()), ('review_notes', sa.Text()), ('reviewed_by', sa.Uuid())]
    for name, col_type in proposal_cols:
        if not column_exists(bind, 'proposals', name):
            op.add_column('proposals', sa.Column(name, col_type, nullable=True))
    op.create_foreign_key('proposals_service_id_fkey', 'proposals', 'services', ['service_id'], ['id'])
    op.create_foreign_key('proposals_reviewed_by_fkey', 'proposals', 'users', ['reviewed_by'], ['id'])
    op.create_index('ix_proposals_service_id', 'proposals', ['service_id'])

    project_cols = [
        ('service_id', sa.Uuid()), ('industry_id', sa.Uuid()),
        ('completion_submitted_at', sa.DateTime(timezone=True)),
        ('client_review_status', sa.String(30)),
        ('client_approved_at', sa.DateTime(timezone=True)),
        ('client_feedback', sa.Text()),
        ('final_delivery_version', sa.Integer()),
    ]
    for name, col_type in project_cols:
        if not column_exists(bind, 'projects', name):
            default = '0' if name == 'final_delivery_version' else None
            op.add_column('projects', sa.Column(name, col_type, nullable=True, server_default=default))
    op.create_foreign_key('projects_service_id_fkey', 'projects', 'services', ['service_id'], ['id'])
    op.create_foreign_key('projects_industry_id_fkey', 'projects', 'industries', ['industry_id'], ['id'])
    op.create_index('ix_projects_service_id', 'projects', ['service_id'])
    op.create_index('ix_projects_industry_id', 'projects', ['industry_id'])


def downgrade() -> None:
    op.drop_index('ix_projects_industry_id', table_name='projects')
    op.drop_index('ix_projects_service_id', table_name='projects')
    op.drop_constraint('projects_industry_id_fkey', 'projects', type_='foreignkey')
    op.drop_constraint('projects_service_id_fkey', 'projects', type_='foreignkey')
    for col in ('final_delivery_version', 'client_feedback', 'client_approved_at', 'client_review_status', 'completion_submitted_at', 'industry_id', 'service_id'):
        op.drop_column('projects', col)

    op.drop_index('ix_proposals_service_id', table_name='proposals')
    op.drop_constraint('proposals_reviewed_by_fkey', 'proposals', type_='foreignkey')
    op.drop_constraint('proposals_service_id_fkey', 'proposals', type_='foreignkey')
    for col in ('reviewed_by', 'review_notes', 'service_id'):
        op.drop_column('proposals', col)

    op.drop_index('ix_leads_industry_id', table_name='leads')
    op.drop_index('ix_leads_service_id', table_name='leads')
    op.drop_constraint('leads_industry_id_fkey', 'leads', type_='foreignkey')
    op.drop_constraint('leads_service_id_fkey', 'leads', type_='foreignkey')
    for col in ('rejection_reason', 'evaluation_result', 'delivery_timeline', 'requirements_confirmed', 'meeting_notes', 'evaluation_date', 'industry_id', 'service_id'):
        op.drop_column('leads', col)

    op.drop_index('ix_contact_submissions_lead_id', table_name='contact_submissions')
    op.drop_index('ix_contact_submissions_industry_id', table_name='contact_submissions')
    op.drop_index('ix_contact_submissions_service_id', table_name='contact_submissions')
    op.drop_constraint('contact_submissions_lead_id_fkey', 'contact_submissions', type_='foreignkey')
    op.drop_constraint('contact_submissions_industry_id_fkey', 'contact_submissions', type_='foreignkey')
    op.drop_constraint('contact_submissions_service_id_fkey', 'contact_submissions', type_='foreignkey')
    for col in ('lead_id', 'requirements', 'expected_budget', 'industry_id', 'service_id'):
        op.drop_column('contact_submissions', col)
    # Postgres does not support dropping enum values — the proposal_status
    # additions are left in place on downgrade.
