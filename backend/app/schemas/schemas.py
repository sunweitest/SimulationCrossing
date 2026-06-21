from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ===== 用户相关 =====
class UserCreate(BaseModel):
    """用户注册"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    """用户登录"""
    identifier: str  # 邮箱或手机号
    password: str


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """令牌响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ===== 角色相关 =====
class CharacterCreate(BaseModel):
    """角色创建"""
    name: str
    gender: str
    age: int = Field(..., ge=18)
    rank: str
    background: Optional[str] = None
    novel: str  # 三国演义/水浒传/明代/清代
    timeline: str
    character_type: str  # preset/custom
    starting_points: int = 0


class CharacterInfo(BaseModel):
    """角色信息"""
    name: str
    gender: str
    age: int
    rank: str
    background: Optional[str]
    novel: str
    timeline: str
    character_type: str
    starting_points: int


# ===== 游戏相关 =====
class GameUpdate(BaseModel):
    """游戏更新"""
    points_awarded: int = 0
    new_achievement: str = ""


class Scene(BaseModel):
    """场景"""
    scene_description: str
    choices: List[str]
    game_update: GameUpdate
    scene_image: Optional[str] = None  # 匹配的场景配图URL，无匹配时为 null


class UserAction(BaseModel):
    """用户行动"""
    action: str
    game_session_id: int


class GameSessionCreate(BaseModel):
    """创建游戏会话"""
    character: CharacterCreate


class GameSessionResponse(BaseModel):
    """游戏会话响应"""
    id: int
    session_id: Optional[str]
    character_name: str
    character_gender: str
    character_age: int
    character_rank: str
    character_background: Optional[str]
    novel: str
    timeline: str
    character_type: str
    points: int
    achievements: List[str]
    current_scene: Optional[dict]
    characters_state: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GameStateResponse(BaseModel):
    """游戏状态响应"""
    points: int
    achievements: List[str]
    scene_count: int
    choice_count: int
    current_scene: Optional[dict]


class GameSessionListItem(BaseModel):
    """游戏会话列表项"""
    id: int
    character_name: str
    character_gender: str
    character_age: int
    character_rank: str
    novel: str
    timeline: str
    character_type: str
    points: int
    achievements: List[str]
    current_scene_desc: Optional[str] = None  # 场景描述预览（前80字）
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== 使用限制相关 =====
class UsageLimitResponse(BaseModel):
    """使用限制响应"""
    remaining_messages: int
    daily_limit: int
    is_logged_in: bool
    needs_login: bool = False


# ===== 角色追踪相关 =====
class CharacterEntry(BaseModel):
    """单个角色追踪条目"""
    name: str
    identity: str = ""
    relationship_to_player: str = ""
    favorability: int = Field(default=0, ge=-100, le=100)
    status: str = "存活"
    last_interaction: Optional[str] = None
    first_appeared_turn: Optional[int] = None


class CharactersState(BaseModel):
    """角色追踪状态"""
    characters: List[CharacterEntry] = Field(default_factory=list)
    last_updated_turn: int = 0


class CharacterInfoResponse(BaseModel):
    """角色查询响应"""
    session_id: int
    total_characters: int
    characters: List[CharacterEntry]
    last_updated_turn: int


# ===== 管理后台：小说/历史背景 =====
class NovelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    sort_order: int = 0


class NovelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class NovelResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    timeline_count: int = 0
    character_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== 管理后台：时间节点 =====
class TimelineCreate(BaseModel):
    novel_id: int
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    sort_order: int = 0


class TimelineUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class TimelineResponse(BaseModel):
    id: int
    novel_id: int
    novel_name: str = ""
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== 管理后台：预设角色 =====
class TimelineEntrySchema(BaseModel):
    """角色时间节点条目"""
    timeline: str = Field(..., min_length=1)
    background: Optional[str] = None
    initial_scene: str = Field(..., min_length=1)


class PresetCharacterAdminCreate(BaseModel):
    novel: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1)
    gender: Optional[str] = None
    age: Optional[int] = None
    rank: Optional[str] = None
    background: Optional[str] = None
    starting_points: int = 0
    timelines: List[TimelineEntrySchema] = Field(default_factory=list)


class PresetCharacterAdminUpdate(BaseModel):
    novel: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    rank: Optional[str] = None
    background: Optional[str] = None
    starting_points: Optional[int] = None
    timelines: Optional[List[TimelineEntrySchema]] = None


class PresetCharacterAdminResponse(BaseModel):
    id: int
    novel: str
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    rank: Optional[str] = None
    background: Optional[str] = None
    starting_points: int = 0
    timelines: List[TimelineEntrySchema] = []

    class Config:
        from_attributes = True


# ===== 公开接口：小说时间节点 =====
class NovelTimelineResponse(BaseModel):
    novel_id: int
    novel_name: str
    description: Optional[str] = None
    timelines: List[str] = []
