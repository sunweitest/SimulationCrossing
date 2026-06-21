from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    game_sessions = relationship("GameSession", back_populates="user", cascade="all, delete-orphan")


class GameSession(Base):
    """游戏会话表"""
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 未登录用户为None
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

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="game_sessions")
    scenes = relationship("SceneHistory", back_populates="game_session", cascade="all, delete-orphan")
    choices = relationship("ChoiceHistory", back_populates="game_session", cascade="all, delete-orphan")


class SceneHistory(Base):
    """场景历史表"""
    __tablename__ = "scene_history"

    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    scene_description = Column(Text, nullable=False)
    choices = Column(JSON)  # 可选择项列表
    points_awarded = Column(Integer, default=0)
    achievement = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    game_session = relationship("GameSession", back_populates="scenes")


class ChoiceHistory(Base):
    """选择历史表"""
    __tablename__ = "choice_history"

    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    choice = Column(Text, nullable=False)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

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

    timelines = relationship("CharacterTimeline", back_populates="character", cascade="all, delete-orphan")


class CharacterTimeline(Base):
    """角色时间节点配置表"""
    __tablename__ = "character_timelines"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("preset_characters.id"), nullable=False)
    timeline = Column(String, nullable=False)
    background = Column(Text)
    initial_scene = Column(Text, nullable=False)

    character = relationship("PresetCharacter", back_populates="timelines")


class NovelConfig(Base):
    """小说/历史背景配置表"""
    __tablename__ = "novel_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    timelines = relationship("TimelineConfig", back_populates="novel", cascade="all, delete-orphan")


class TimelineConfig(Base):
    """时间节点配置表"""
    __tablename__ = "timeline_configs"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novel_configs.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    novel = relationship("NovelConfig", back_populates="timelines")
