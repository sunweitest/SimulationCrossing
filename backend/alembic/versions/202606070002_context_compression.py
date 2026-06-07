"""add context compression columns to game_sessions

Revision ID: 202606070002
Revises: 202606070001
Create Date: 2026-06-07 13:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202606070002"
down_revision = "202606070001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("running_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "game_sessions",
        sa.Column("summary_turn_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade():
    op.drop_column("game_sessions", "summary_turn_count")
    op.drop_column("game_sessions", "running_summary")
