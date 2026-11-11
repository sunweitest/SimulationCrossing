"""用户提「想穿越的世界」

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_world_suggestions_id", "world_suggestions", ["id"])
    op.create_index("ix_world_suggestions_user_id", "world_suggestions", ["user_id"])
    op.create_index("ix_world_suggestions_created_at", "world_suggestions", ["created_at"])
    op.create_index(
        "ix_world_suggestions_status_created", "world_suggestions", ["status", "created_at"]
    )

    op.create_table(
        "world_suggestion_votes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "suggestion_id",
            sa.Integer(),
            sa.ForeignKey("world_suggestions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("voter_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("voter_key", "suggestion_id", name="uq_world_suggestion_votes_key"),
    )
    op.create_index("ix_world_suggestion_votes_id", "world_suggestion_votes", ["id"])
    op.create_index(
        "ix_world_suggestion_votes_suggestion_id", "world_suggestion_votes", ["suggestion_id"]
    )


def downgrade() -> None:
    op.drop_table("world_suggestion_votes")
    op.drop_table("world_suggestions")
