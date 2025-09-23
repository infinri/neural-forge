"""Add governance token metrics table

Revision ID: 0003_governance_token_metrics
Revises: 0002_pgvector_embeddings
Create Date: 2025-08-20 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_governance_token_metrics"
down_revision = "0002_pgvector_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_token_metrics",
        sa.Column("token_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False, server_default=sa.text("'global'")),
        sa.Column("activation_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("effectiveness_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("token_id", "project_id"),
    )
    op.create_index(
        "idx_token_metrics_project_updated",
        "governance_token_metrics",
        ["project_id", "updated_at"],
    )
    op.create_index(
        "idx_token_metrics_activation",
        "governance_token_metrics",
        ["activation_count"],
    )


def downgrade() -> None:
    op.drop_index("idx_token_metrics_activation", table_name="governance_token_metrics")
    op.drop_index("idx_token_metrics_project_updated", table_name="governance_token_metrics")
    op.drop_table("governance_token_metrics")
