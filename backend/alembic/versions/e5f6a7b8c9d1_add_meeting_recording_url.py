"""Add recording_url to meetings

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-08-24 00:00:00.000000

UAT closure pass §8 (remaining gaps): doc §13 — "If meetings are recorded,
the recording and/or meeting notes should be stored according to the
applicable access permissions." Meeting.notes already existed with a
working access path; recordings had no field at all. This adds a URL
column (the file itself lives in existing private object storage), sharing
the same MeetingOut visibility notes already uses rather than a new path.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d1'
down_revision: Union[str, None] = 'd4e5f6a7b8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in [c['name'] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()
    if not column_exists(bind, 'meetings', 'recording_url'):
        op.add_column('meetings', sa.Column('recording_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, 'meetings', 'recording_url'):
        op.drop_column('meetings', 'recording_url')
