"""使命系统：character_timelines.mission + game_sessions.mission_state

Revision ID: b7c1e2d3f4a5
Revises: 9f2c7d1a4b30
Create Date: 2026-11-03 16:50:00
"""
from alembic import op
import sqlalchemy as sa


revision = "b7c1e2d3f4a5"
down_revision = "9f2c7d1a4b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 角色 × 时间节点上的使命定义（title / goal / stages / deadline_turns / stakes）
    op.add_column("character_timelines", sa.Column("mission", sa.JSON(), nullable=True))
    # 一次游戏里的使命进度（stage_index / days_left / status / log）
    op.add_column("game_sessions", sa.Column("mission_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_sessions", "mission_state")
    op.drop_column("character_timelines", "mission")
