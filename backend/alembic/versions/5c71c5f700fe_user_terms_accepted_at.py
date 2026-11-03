"""users.terms_accepted_at（注册同意条款留痕）

Revision ID: 5c71c5f700fe
Revises: 62366e48b269
Create Date: 2026-11-03 13:13:38.231942

顺带把 summary_turn_count 收紧为 NOT NULL（模型里一直是 nullable=False，
库里是 nullable，属于历史漂移；现有数据已全部回填 0）。
"""
from alembic import op
import sqlalchemy as sa


revision = '5c71c5f700fe'
down_revision = '62366e48b269'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE game_sessions SET summary_turn_count = 0 WHERE summary_turn_count IS NULL")
    op.alter_column('game_sessions', 'summary_turn_count',
                    existing_type=sa.INTEGER(),
                    nullable=False,
                    existing_server_default=sa.text('0'))


def downgrade():
    op.alter_column('game_sessions', 'summary_turn_count',
                    existing_type=sa.INTEGER(),
                    nullable=True,
                    existing_server_default=sa.text('0'))
    op.drop_column('users', 'terms_accepted_at')
