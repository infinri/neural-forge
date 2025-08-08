"""
Initial schema (v1.3)

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-08 01:20:00
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # memory_entries
    op.create_table(
        'memory_entries',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('project_id', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('quarantined', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_memory_project_created', 'memory_entries', ['project_id', 'created_at'])

    # tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('project_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('idx_tasks_project_status', 'tasks', ['project_id', 'status'])

    # diffs
    op.create_table(
        'diffs',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('project_id', sa.Text(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('diff', sa.Text(), nullable=False),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_diffs_project_created', 'diffs', ['project_id', 'created_at'])

    # errors
    op.create_table(
        'errors',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('project_id', sa.Text(), nullable=True),
        sa.Column('level', sa.Text(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_errors_level_created', 'errors', ['level', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_errors_level_created', table_name='errors')
    op.drop_table('errors')

    op.drop_index('idx_diffs_project_created', table_name='diffs')
    op.drop_table('diffs')

    op.drop_index('idx_tasks_project_status', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('idx_memory_project_created', table_name='memory_entries')
    op.drop_table('memory_entries')
