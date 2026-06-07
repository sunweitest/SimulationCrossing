"""initial schema

Revision ID: 202605310001
Revises:
Create Date: 2026-05-31 10:00:01
"""
from alembic import op
import sqlalchemy as sa

revision = "202605310001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("character_name", sa.String(), nullable=False),
        sa.Column("character_gender", sa.String(), nullable=True),
        sa.Column("character_age", sa.Integer(), nullable=True),
        sa.Column("character_rank", sa.String(), nullable=True),
        sa.Column("character_background", sa.Text(), nullable=True),
        sa.Column("novel", sa.String(), nullable=False),
        sa.Column("timeline", sa.String(), nullable=False),
        sa.Column("character_type", sa.String(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("achievements", sa.JSON(), nullable=True),
        sa.Column("current_scene", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_game_sessions_id"), "game_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_game_sessions_session_id"), "game_sessions", ["session_id"], unique=True)

    op.create_table(
        "choice_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_session_id", sa.Integer(), nullable=False),
        sa.Column("choice", sa.Text(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_choice_history_id"), "choice_history", ["id"], unique=False)

    op.create_table(
        "scene_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_session_id", sa.Integer(), nullable=False),
        sa.Column("scene_description", sa.Text(), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=True),
        sa.Column("points_awarded", sa.Integer(), nullable=True),
        sa.Column("achievement", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scene_history_id"), "scene_history", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_scene_history_id"), table_name="scene_history")
    op.drop_table("scene_history")
    op.drop_index(op.f("ix_choice_history_id"), table_name="choice_history")
    op.drop_table("choice_history")
    op.drop_index(op.f("ix_game_sessions_session_id"), table_name="game_sessions")
    op.drop_index(op.f("ix_game_sessions_id"), table_name="game_sessions")
    op.drop_table("game_sessions")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
