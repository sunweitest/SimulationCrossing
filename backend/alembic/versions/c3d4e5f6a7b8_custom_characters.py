"""自定义角色私有存档

Revision ID: c3d4e5f6a7b8
Revises: b7c1e2d3f4a5
Create Date: 2026-11-03 19:20:00
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b7c1e2d3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("novel", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("rank", sa.String(), nullable=True),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_custom_characters_user_id", "custom_characters", ["user_id"])
    op.create_index("ix_custom_characters_novel", "custom_characters", ["novel"])


def downgrade() -> None:
    op.drop_index("ix_custom_characters_novel", table_name="custom_characters")
    op.drop_index("ix_custom_characters_user_id", table_name="custom_characters")
    op.drop_table("custom_characters")
