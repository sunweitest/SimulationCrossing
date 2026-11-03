"""回合序号 + 场景配图 + 外键索引 + 时间统一北京时区

Revision ID: 62366e48b269
Revises: 202610300001
Create Date: 2026-11-03 12:03:16.125723

包含四件事：
1. scene_history / choice_history 增加 turn_index（回合序号），并按历史顺序回填
2. scene_history 增加 scene_image（回溯时用来还原配图）
3. 5 个外键列加索引（user_id / game_session_id ×2 / character_id / novel_id）
4. 历史时间从 UTC 平移 8 小时到北京时间（库里是 timestamp without time zone，
   之前用 datetime.utcnow 写入，展示会少 8 小时）
"""
from alembic import op
import sqlalchemy as sa


revision = '62366e48b269'
down_revision = '202610300001'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. 新列（先带默认值，回填后再去掉） ──
    op.add_column('scene_history', sa.Column('turn_index', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scene_history', sa.Column('scene_image', sa.String(), nullable=True))
    op.add_column('choice_history', sa.Column('turn_index', sa.Integer(), nullable=False, server_default='0'))

    # ── 2. 回填 turn_index：会话内按创建时间排序，开局为 0 ──
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (PARTITION BY game_session_id ORDER BY created_at, id) - 1 AS idx
            FROM scene_history
        )
        UPDATE scene_history sh SET turn_index = ranked.idx
        FROM ranked WHERE sh.id = ranked.id;
    """)
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (PARTITION BY game_session_id ORDER BY created_at, id) AS idx
            FROM choice_history
        )
        UPDATE choice_history ch SET turn_index = ranked.idx
        FROM ranked WHERE ch.id = ranked.id;
    """)

    # ── 3. 索引 ──
    op.create_index('ix_game_sessions_user_id', 'game_sessions', ['user_id'], unique=False)
    op.create_index('ix_scene_history_game_session_id', 'scene_history', ['game_session_id'], unique=False)
    op.create_index('ix_choice_history_game_session_id', 'choice_history', ['game_session_id'], unique=False)
    op.create_index('ix_character_timelines_character_id', 'character_timelines', ['character_id'], unique=False)
    op.create_index('ix_timeline_configs_novel_id', 'timeline_configs', ['novel_id'], unique=False)
    # 回溯面板按 (session, turn) 取数据，复合索引比单列 turn_index 更有用
    op.create_index('ix_scene_history_session_turn', 'scene_history', ['game_session_id', 'turn_index'], unique=False)

    # ── 4. 历史数据：UTC → 北京时间（+8h，只执行一次） ──
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name IN ('created_at', 'updated_at')
            LOOP
                EXECUTE format(
                    'UPDATE %I SET %I = %I + interval ''8 hours'' WHERE %I IS NOT NULL',
                    r.table_name, r.column_name, r.column_name, r.column_name
                );
            END LOOP;
        END $$;
    """)

    # ── 5. 收尾：去掉 server_default，summary_turn_count 补空值并收紧为 NOT NULL ──
    op.alter_column('scene_history', 'turn_index', server_default=None)
    op.alter_column('choice_history', 'turn_index', server_default=None)
    op.execute("UPDATE game_sessions SET summary_turn_count = 0 WHERE summary_turn_count IS NULL")
    op.alter_column('game_sessions', 'summary_turn_count',
                    existing_type=sa.Integer(),
                    nullable=False,
                    existing_server_default=sa.text('0'))


def downgrade():
    op.drop_index('ix_scene_history_session_turn', table_name='scene_history')
    op.drop_index('ix_timeline_configs_novel_id', table_name='timeline_configs')
    op.drop_index('ix_character_timelines_character_id', table_name='character_timelines')
    op.drop_index('ix_choice_history_game_session_id', table_name='choice_history')
    op.drop_index('ix_scene_history_game_session_id', table_name='scene_history')
    op.drop_index('ix_game_sessions_user_id', table_name='game_sessions')
    op.drop_column('choice_history', 'turn_index')
    op.drop_column('scene_history', 'scene_image')
    op.drop_column('scene_history', 'turn_index')
    op.alter_column('game_sessions', 'summary_turn_count',
                    existing_type=sa.Integer(),
                    nullable=True,
                    existing_server_default=sa.text('0'))
