from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from app.core.timeutil import now_cn
from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # 注册时勾选同意《服务条款》《隐私政策》的时间（合规留痕）
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_cn)

    # 关系
    game_sessions = relationship("GameSession", back_populates="user", cascade="all, delete-orphan")


class GameSession(Base):
    """游戏会话表"""
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 未登录用户为None
    session_id = Column(String, unique=True, index=True, nullable=True)  # LLM会话ID

    # 角色信息
    character_name = Column(String, nullable=False)
    character_gender = Column(String)
    character_age = Column(Integer)
    character_rank = Column(String)
    character_background = Column(Text)
    novel = Column(String, nullable=False)  # 三国演义/水浒传/明代/清代
    timeline = Column(String, nullable=False)
    character_type = Column(String)  # preset/custom

    # 游戏状态
    points = Column(Integer, default=0)
    achievements = Column(JSON, default=list)  # 成就列表
    current_scene = Column(JSON)  # 当前场景

    # 上下文压缩
    running_summary = Column(Text, nullable=True)  # 压缩后的故事概要
    summary_turn_count = Column(Integer, default=0)  # 已压缩的对话轮数

    # 结构化角色追踪
    characters_state = Column(JSON, nullable=True)  # {"characters": [...], "last_updated_turn": N}

    # 使命进度：{title, goal, stages, stage_index, deadline_turns, days_left, status, last_note}
    mission_state = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=now_cn)
    updated_at = Column(DateTime, default=now_cn, onupdate=now_cn)

    # 关系
    user = relationship("User", back_populates="game_sessions")
    scenes = relationship("SceneHistory", back_populates="game_session", cascade="all, delete-orphan")
    choices = relationship("ChoiceHistory", back_populates="game_session", cascade="all, delete-orphan")


class SceneHistory(Base):
    """场景历史表"""
    __tablename__ = "scene_history"
    __table_args__ = (
        Index("ix_scene_history_session_turn", "game_session_id", "turn_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False, default=0)  # 第几回合，0=开局
    scene_description = Column(Text, nullable=False)
    choices = Column(JSON)  # 可选择项列表
    points_awarded = Column(Integer, default=0)
    achievement = Column(String)
    scene_image = Column(String)  # 该回合配图，回滚时用来还原 current_scene
    created_at = Column(DateTime, default=now_cn)

    # 关系
    game_session = relationship("GameSession", back_populates="scenes")


class ChoiceHistory(Base):
    """选择历史表"""
    __tablename__ = "choice_history"

    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False, default=0)  # 与 scene_history 同回合对齐
    choice = Column(Text, nullable=False)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_cn)

    # 关系
    game_session = relationship("GameSession", back_populates="choices")


class PresetCharacter(Base):
    """预设角色表"""
    __tablename__ = "preset_characters"

    id = Column(Integer, primary_key=True, index=True)
    novel = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    gender = Column(String)
    age = Column(Integer)
    rank = Column(String)
    background = Column(Text)
    starting_points = Column(Integer, default=0)
    # 小人物标记：跑龙套、差役、丫鬟、小妖这类角色，给用户更多代入感
    is_minor = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    # 角色头像（相对 public 的路径，如 /images/characters/红楼梦/贾宝玉.webp）
    image = Column(String, nullable=True)

    timelines = relationship("CharacterTimeline", back_populates="character", cascade="all, delete-orphan")


class CharacterTimeline(Base):
    """角色时间节点配置表"""
    __tablename__ = "character_timelines"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("preset_characters.id"), nullable=False, index=True)
    timeline = Column(String, nullable=False)
    background = Column(Text)
    initial_scene = Column(Text, nullable=False)
    # 使命：{title, goal, stages:[{name, detail}], deadline_turns, stakes}
    mission = Column(JSON, nullable=True)

    character = relationship("PresetCharacter", back_populates="timelines")


class NovelConfig(Base):
    """小说/历史背景配置表"""
    __tablename__ = "novel_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_cn)

    timelines = relationship("TimelineConfig", back_populates="novel", cascade="all, delete-orphan")


class TimelineConfig(Base):
    """时间节点配置表"""
    __tablename__ = "timeline_configs"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novel_configs.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_cn)

    novel = relationship("NovelConfig", back_populates="timelines")


class WorldClickEvent(Base):
    """世界卡点击埋点：哪个世界被点开最多"""
    __tablename__ = "world_click_events"

    id = Column(Integer, primary_key=True, index=True)
    novel = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_guest = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    client_ip = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now_cn, index=True)


class WorldVote(Base):
    """「想看哪个世界」投票：同一 voter_key 对同一世界只算一票"""
    __tablename__ = "world_votes"

    id = Column(Integer, primary_key=True, index=True)
    world_name = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voter_key = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now_cn)

    __table_args__ = (
        UniqueConstraint("voter_key", "world_name", name="uq_world_votes_voter_world"),
    )


class CustomCharacter(Base):
    """玩家自定义角色：只有创建者本人可见，可改可删。"""
    __tablename__ = "custom_characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    novel = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    gender = Column(String)
    age = Column(Integer)
    rank = Column(String)
    background = Column(Text)
    created_at = Column(DateTime, default=now_cn)
    updated_at = Column(DateTime, default=now_cn, onupdate=now_cn)

    user = relationship("User")
