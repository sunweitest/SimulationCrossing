"""preset_characters: 增加 is_minor / image；新增世界点击埋点与投票表

Revision ID: 9f2c7d1a4b30
Revises: 5c71c5f700fe
Create Date: 2026-11-03 16:05:00
"""
from alembic import op
import sqlalchemy as sa


revision = "9f2c7d1a4b30"
down_revision = "5c71c5f700fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 角色：小人物标记 + 头像
    op.add_column(
        "preset_characters",
        sa.Column("is_minor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("preset_characters", sa.Column("image", sa.String(), nullable=True))
    op.create_index(
        "ix_preset_characters_is_minor", "preset_characters", ["is_minor"], unique=False
    )

    # 世界卡点击埋点
    op.create_table(
        "world_click_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("novel", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("client_ip", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_world_click_events_novel", "world_click_events", ["novel"])
    op.create_index("ix_world_click_events_created_at", "world_click_events", ["created_at"])

    # 「想看哪个世界」投票：同一 voter_key 对同一世界只算一票
    op.create_table(
        "world_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("world_name", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("voter_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("voter_key", "world_name", name="uq_world_votes_voter_world"),
    )
    op.create_index("ix_world_votes_world_name", "world_votes", ["world_name"])


def downgrade() -> None:
    op.drop_index("ix_world_votes_world_name", table_name="world_votes")
    op.drop_table("world_votes")
    op.drop_index("ix_world_click_events_created_at", table_name="world_click_events")
    op.drop_index("ix_world_click_events_novel", table_name="world_click_events")
    op.drop_table("world_click_events")
    op.drop_index("ix_preset_characters_is_minor", table_name="preset_characters")
    op.drop_column("preset_characters", "image")
    op.drop_column("preset_characters", "is_minor")
