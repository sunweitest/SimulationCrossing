"""用户昵称（天梯展示用，不展示邮箱/手机号）

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-11 12:40:00
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 可空：老用户不强制改名，天梯按「闯关者 + id」兜底
    op.add_column("users", sa.Column("nickname", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "nickname")
