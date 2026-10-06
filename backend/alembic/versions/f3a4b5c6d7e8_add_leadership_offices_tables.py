"""Add leadership and offices tables

Revision ID: f3a4b5c6d7e8
Revises: 1c50833911b9
Create Date: 2026-08-24 00:00:00.000000

Adds two new simple-CMS-resource tables (same shape as `awards`/
`testimonials`): `leadership` (About page "Executive Leadership" grid) and
`offices` (About page "Global Presence" section). Both were previously
hardcoded in frontend/src/data/about.js with no backend model.

No changes to any existing table. The singleton "company info" / "about
page content" blobs (mission, tagline, HQ address, core values, timeline,
certifications) reuse the existing `settings` table (key="company_info" /
"about_content") instead of new tables — no migration needed for those.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = '1c50833911b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, 'leadership'):
        op.create_table(
            'leadership',
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('title', sa.String(length=150), nullable=False),
            sa.Column('bio', sa.Text(), nullable=True),
            sa.Column('photo_url', sa.String(length=500), nullable=True),
            sa.Column('linkedin', sa.String(length=500), nullable=True),
            sa.Column('order', sa.Integer(), nullable=False),
            sa.Column('is_published', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not table_exists(bind, 'offices'):
        op.create_table(
            'offices',
            sa.Column('city', sa.String(length=150), nullable=False),
            sa.Column('country', sa.String(length=150), nullable=True),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('is_headquarters', sa.Boolean(), nullable=False),
            sa.Column('order', sa.Integer(), nullable=False),
            sa.Column('is_published', sa.Boolean(), nullable=False),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, 'offices'):
        op.drop_table('offices')
    if table_exists(bind, 'leadership'):
        op.drop_table('leadership')
