"""Add Partner Portal (partner_accounts, partner_files, tickets.partner_account_id, 'partner' user role)

Per the workflow PDF's Client Portal pattern, mirrored for a login-gated
Partner Portal (self-service + admin management) — distinct from the
pre-existing `partners` table, which is the public "our partners" CMS logo
listing, not an account. Reuses the existing `partner_type` enum (already
created for that CMS table) rather than defining a new one, since its values
(technology_partner/business_partner/reseller) already fit a partner
*account*'s category too.

`ALTER TYPE ... ADD VALUE` cannot run inside the same transaction as anything
that uses the new value, and on some PostgreSQL/driver combinations cannot
run inside a transaction block at all — hence the explicit autocommit block
for that one statement, verified by running this migration against a real
Postgres container (not assumed to work from documentation alone).

Revision ID: 7130a92059c9
Revises: 4a2dbc43345c
Create Date: 2026-08-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '7130a92059c9'
down_revision: Union[str, None] = '4a2dbc43345c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'partner'")

    op.create_table(
        'partner_accounts',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('partnership_type', postgresql.ENUM('technology_partner', 'business_partner', 'reseller', name='partner_type', create_type=False), nullable=False),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('account_manager_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_manager_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_partner_accounts_account_manager_id', 'partner_accounts', ['account_manager_id'], unique=False)

    op.create_table(
        'partner_files',
        sa.Column('partner_account_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('file_url', sa.String(length=500), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=150), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['partner_account_id'], ['partner_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_partner_files_partner_account_id', 'partner_files', ['partner_account_id'], unique=False)

    op.add_column('tickets', sa.Column('partner_account_id', sa.UUID(), nullable=True))
    op.create_foreign_key('tickets_partner_account_id_fkey', 'tickets', 'partner_accounts', ['partner_account_id'], ['id'])
    op.create_index('ix_tickets_partner_account_id', 'tickets', ['partner_account_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tickets_partner_account_id', table_name='tickets')
    op.drop_constraint('tickets_partner_account_id_fkey', 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'partner_account_id')
    op.drop_table('partner_files')
    op.drop_table('partner_accounts')
    # Postgres does not support dropping a single enum value — the 'partner'
    # value added to user_role is left in place on downgrade.
