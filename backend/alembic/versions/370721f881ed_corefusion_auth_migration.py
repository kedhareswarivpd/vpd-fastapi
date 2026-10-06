"""CoreFusion-owned auth: password_hash + lockout fields on users, user_sessions,
password_reset_tokens, email_verification_tokens (replaces Supabase Auth as
the identity/session/credential source of truth)

`password_hash` is added NOT NULL, which requires a two-step approach on a
table with existing rows (added nullable -> backfilled -> constrained NOT
NULL) since there's no plaintext password to hash for accounts that were
authenticated via Supabase Auth up to this point. Existing users are
backfilled with a random, unusable Argon2id hash — `verify_password` will
never match it, which means the pre-existing accounts require the
`forgot-password` flow to set a real, usable password after this migration.
This is a genuine migration consideration, documented in
`docs/BACKEND_GAPS_AND_ISSUES.md`, not something this migration file can
resolve alone (this app never had these users' plaintext passwords — Supabase
Auth held those, not us).

Revision ID: 370721f881ed
Revises: 7130a92059c9
Create Date: 2026-08-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '370721f881ed'
down_revision: Union[str, None] = '7130a92059c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- users: new auth-owned columns ----------
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

    # Backfill: existing (pre-migration, Supabase-authenticated) users get a
    # random, unusable Argon2id-*shaped* hash of a value nobody has ever
    # typed — see the module docstring above for why this is unavoidable,
    # and what the account owner needs to do about it (forgot-password).
    # `gen_random_uuid()` (core Postgres 13+, no extension required) is used
    # as the randomness source rather than pgcrypto's `gen_random_bytes()`,
    # which isn't enabled on every Postgres instance this migration might
    # run against (confirmed missing on this project's own local dev
    # Postgres — caught by actually running this migration, not assumed).
    op.execute(
        "UPDATE users SET password_hash = "
        "'$argon2id$v=19$m=19456,t=2,p=1$' || replace(gen_random_uuid()::text, '-', '') || "
        "'$' || replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '') "
        "WHERE password_hash IS NULL"
    )
    op.alter_column('users', 'password_hash', nullable=False)

    # ---------- user_sessions ----------
    op.create_table(
        'user_sessions',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
        sa.Column('previous_refresh_token_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token_hash'),
        sa.UniqueConstraint('refresh_token_hash'),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_session_token_hash', 'user_sessions', ['session_token_hash'], unique=True)
    op.create_index('ix_user_sessions_refresh_token_hash', 'user_sessions', ['refresh_token_hash'], unique=True)
    op.create_index('ix_user_sessions_previous_refresh_token_hash', 'user_sessions', ['previous_refresh_token_hash'], unique=False)

    # ---------- password_reset_tokens ----------
    op.create_table(
        'password_reset_tokens',
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
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)

    # ---------- email_verification_tokens ----------
    op.create_table(
        'email_verification_tokens',
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
    op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'], unique=False)
    op.create_index('ix_email_verification_tokens_token_hash', 'email_verification_tokens', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('email_verification_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('user_sessions')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'is_locked')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'password_hash')
