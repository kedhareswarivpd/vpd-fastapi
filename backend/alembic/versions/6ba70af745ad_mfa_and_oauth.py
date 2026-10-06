"""Add MFA (TOTP) columns/tables and OAuth account linking table.

Both features are OFF by default (settings.mfa_enabled / settings.oauth_enabled
in core/config.py) — this migration only adds the schema; nothing here turns
either feature on for any account or environment.

Revision ID: 6ba70af745ad
Revises: 370721f881ed
Create Date: 2026-08-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '6ba70af745ad'
down_revision: Union[str, None] = '370721f881ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- users: MFA columns ----------
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('mfa_secret_encrypted', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))

    # ---------- mfa_backup_codes ----------
    op.create_table(
        'mfa_backup_codes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_hash'),
    )
    op.create_index('ix_mfa_backup_codes_user_id', 'mfa_backup_codes', ['user_id'], unique=False)
    op.create_index('ix_mfa_backup_codes_code_hash', 'mfa_backup_codes', ['code_hash'], unique=True)

    # ---------- mfa_challenges ----------
    op.create_table(
        'mfa_challenges',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_mfa_challenges_user_id', 'mfa_challenges', ['user_id'], unique=False)
    op.create_index('ix_mfa_challenges_token_hash', 'mfa_challenges', ['token_hash'], unique=True)

    # ---------- oauth_accounts ----------
    op.create_table(
        'oauth_accounts',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('provider_account_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_account_id', name='uq_oauth_provider_account'),
    )
    op.create_index('ix_oauth_accounts_user_id', 'oauth_accounts', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('oauth_accounts')
    op.drop_table('mfa_challenges')
    op.drop_table('mfa_backup_codes')
    op.drop_column('users', 'mfa_enabled_at')
    op.drop_column('users', 'mfa_secret_encrypted')
    op.drop_column('users', 'mfa_enabled')
