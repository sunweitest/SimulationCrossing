"""add characters_state JSON column to game_sessions

Revision ID: 202606140002
Revises: 202606140001
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "202606140002"
down_revision = "202606140001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("characters_state", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("game_sessions", "characters_state")
