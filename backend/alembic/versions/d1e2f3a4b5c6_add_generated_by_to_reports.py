"""Add missing columns to reports table

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-07-09 11:30:00.000000

This migration adds the missing columns to the `reports` table:
- generated_by: UUID foreign key to users table
- file_url: String for file path
- size_bytes: Integer for file size
- deleted_at: Timestamp for soft deletes

The table was created with a different schema than the model expected,
causing 500 errors in the /api/v1/reports/generate endpoint.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    bind = op.get_bind()
    
    # Add generated_by column if it doesn't exist
    if not column_exists(bind, 'reports', 'generated_by'):
        op.add_column('reports', sa.Column('generated_by', sa.UUID(), nullable=True))
        op.create_foreign_key(
            'fk_reports_generated_by',
            'reports',
            'users',
            ['generated_by'],
            ['id']
        )
    
    # Add file_url column if it doesn't exist
    if not column_exists(bind, 'reports', 'file_url'):
        op.add_column('reports', sa.Column('file_url', sa.String(length=500), nullable=True))
    
    # Add size_bytes column if it doesn't exist
    if not column_exists(bind, 'reports', 'size_bytes'):
        op.add_column('reports', sa.Column('size_bytes', sa.Integer(), nullable=True))
    
    # Add deleted_at column if it doesn't exist
    if not column_exists(bind, 'reports', 'deleted_at'):
        op.add_column('reports', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    
    # Drop foreign key constraint and columns if they exist
    if column_exists(bind, 'reports', 'generated_by'):
        op.drop_constraint('fk_reports_generated_by', 'reports', type_='foreignkey')
        op.drop_column('reports', 'generated_by')
    
    if column_exists(bind, 'reports', 'file_url'):
        op.drop_column('reports', 'file_url')
    
    if column_exists(bind, 'reports', 'size_bytes'):
        op.drop_column('reports', 'size_bytes')
    
    if column_exists(bind, 'reports', 'deleted_at'):
        op.drop_column('reports', 'deleted_at')
