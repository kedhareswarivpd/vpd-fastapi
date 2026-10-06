"""add gallery faqs deliverables downloads fields

Revision ID: 662b74e1f2df
Revises: 664442caaa34
Create Date: 2026-08-23 10:52:40.547181

Hand-trimmed from the raw `alembic revision --autogenerate` output: the
autogenerate diff also picked up ~50 unrelated "drop index" / "drop unique
constraint" operations across the whole schema (pre-existing drift between
the DB and the declared models, not something this change touches) — those
are intentionally left out so this migration only does what its message
says: add the new content-schema columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '662b74e1f2df'
down_revision: Union[str, None] = '664442caaa34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_studies', sa.Column('downloads', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('projects', sa.Column('deliverables', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('projects', sa.Column('gallery', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('projects', sa.Column('downloads', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('services', sa.Column('gallery', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('services', sa.Column('faqs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Backfill existing rows so the read schemas (which declare these as
    # plain `list[...] = []`, matching every other array/JSONB field on
    # these models, not `| None`) don't choke on NULL for rows that
    # predate this migration.
    op.execute("UPDATE case_studies SET downloads = '[]'::jsonb WHERE downloads IS NULL")
    op.execute("UPDATE projects SET deliverables = '{}' WHERE deliverables IS NULL")
    op.execute("UPDATE projects SET gallery = '{}' WHERE gallery IS NULL")
    op.execute("UPDATE projects SET downloads = '[]'::jsonb WHERE downloads IS NULL")
    op.execute("UPDATE services SET gallery = '{}' WHERE gallery IS NULL")
    op.execute("UPDATE services SET faqs = '[]'::jsonb WHERE faqs IS NULL")


def downgrade() -> None:
    op.drop_column('services', 'faqs')
    op.drop_column('services', 'gallery')
    op.drop_column('projects', 'downloads')
    op.drop_column('projects', 'gallery')
    op.drop_column('projects', 'deliverables')
    op.drop_column('case_studies', 'downloads')
