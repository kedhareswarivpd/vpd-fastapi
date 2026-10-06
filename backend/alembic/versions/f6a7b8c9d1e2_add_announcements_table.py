"""Add announcements table

Revision ID: f6a7b8c9d1e2
Revises: e5f6a7b8c9d1
Create Date: 2026-08-24 00:00:00.000000

UAT closure pass (remaining gaps): the workflow doc names "Announcements"
as a CMS content type (alongside Services/Industries/Blogs/FAQs/Case
Studies) but no model, router, or frontend existed for it anywhere.
Follows the exact same simple shared-factory pattern as Award/Testimonial.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d1e2'
down_revision: Union[str, None] = 'e5f6a7b8c9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, 'announcements'):
        op.create_table(
            'announcements',
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, 'announcements'):
        op.drop_table('announcements')
