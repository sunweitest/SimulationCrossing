from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from typing import Optional, List
from datetime import datetime


# ===== 用户相关 =====
class UserCreate(BaseModel):
    """注册请求：邮箱与手机号至少提供一个，必须同意条款。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "player@example.com",
                "password": "MyPassw0rd",
                "agree_terms": True,
            }
        }
    )
    """用户注册"""
    email: Optional[EmailStr] = Field(None, description="邮箱，与 phone 至少填一个")
    phone: Optional[str] = Field(None, description="手机号，与 email 至少填一个")
    password: str = Field(..., min_length=6, description="登录密码，至少 6 位")
    # 必须勾选同意《服务条款》《隐私政策》才能注册
    agree_terms: bool = Field(False, description="必须为 true，表示已同意《服务条款》《隐私政策》")


class UserLogin(BaseModel):
    """登录请求。"""
    """用户登录"""
    identifier: str = Field(..., description="邮箱或手机号")
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
    """开局时的角色设定。

    `character_type` 为 `preset` 时，服务端按 世界+角色名+时间节点 取设定，
    只信任 name / novel / timeline；为 `custom` 时使用这里填写的全部字段。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "novel": "废土末世",
                "name": "林哲",
                "gender": "男性",
                "age": 28,
                "rank": "工程师",
                "background": "",
                "timeline": "大断电",
                "character_type": "preset",
            }
        }
    )
    """角色创建

    age 下限只对自定义角色生效（守 18 岁合规线）；预设角色沿用原著年龄，
    贾宝玉 15 岁、哪吒 12 岁这类不能因为年龄校验被挡在门外。
    """
    name: str = Field(..., description="角色名；preset 时必须与预设角色一致")
    gender: str = Field(..., description="性别")
    age: int = Field(..., ge=1, description="年龄（自定义角色要求 ≥1，页面默认 ≥18）")
    rank: str = Field(..., description="身份，如 皇帝 / 士兵 / 丫鬟")
    background: Optional[str] = Field(None, description="角色背景，自定义角色会据此生成使命")
    novel: str = Field(..., description="世界名，如 三国演义 / 红楼梦 / 废土末世")
    timeline: str = Field(..., description="时间节点，需在该世界的时间节点列表内")
    character_type: str = Field(..., description="preset（预设角色）或 custom（自定义角色）")
    starting_points: int = 0

    @model_validator(mode="after")
    def _age_gate(self):
        if self.character_type != "preset" and self.age < 18:
            raise ValueError("自定义角色年龄需满 18 岁")
        return self


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
    scene_description: str = Field(..., description="本回合剧情全文")
    choices: List[str] = Field(..., description="系统给出的 3 个行动选项")
    game_update: GameUpdate
    scene_image: Optional[str] = Field(None, description="匹配到的场景配图 URL，无匹配为 null")
    mission: Optional[dict] = Field(None, description="使命进度（阶段、剩余回合、本回合判定）")
    mission_achievements: Optional[List[str]] = None  # 本回合解锁的使命成就：{title, goal, stage_index, stages, days_left, status, last_label}


class UserAction(BaseModel):
    """一次行动请求。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"game_session_id": 42, "action": "我蹲下去，先看清地上那串脚印"}
        }
    )

    action: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="玩家行动，去除首尾空白后不能为空，最长 200 字",
    )
    game_session_id: int = Field(..., description="对局 id（创建对局时返回的 id）")


class RewindRequest(BaseModel):
    """回合回溯：回到第 turn_index 回合（之后的回合会被丢弃）。"""

    turn_index: int = Field(..., description="目标回合序号，0 表示开局；负数由接口返回 400")


class GameSessionCreate(BaseModel):
    """创建游戏会话"""
    character: CharacterCreate


class GameSessionResponse(BaseModel):
    """游戏会话响应"""
    id: int = Field(..., description="对局 id，后续行动 / 回溯接口都用它")
    session_id: Optional[str] = Field(None, description="模型会话标识，首次调用模型后生成")
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
    mission_state: Optional[dict] = None
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
    """新建世界（管理后台）。"""

    name: str = Field(..., min_length=1, max_length=100, description="世界名，全局唯一")
    description: Optional[str] = Field(None, description="一句话简介")
    sort_order: int = Field(0, description="列表排序，越小越靠前")


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
    """新建时间节点（管理后台）。"""

    novel_id: int = Field(..., description="所属世界 id")
    name: str = Field(..., min_length=1, max_length=100, description="节点名，如 赤壁之战")
    description: Optional[str] = Field(None, description="局势说明")
    sort_order: int = Field(0, description="节点排序")


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
    """角色在某个时间节点的设定。"""

    timeline: str = Field(..., min_length=1, description="时间节点名")
    background: Optional[str] = Field(None, description="该节点下这个角色的处境")
    initial_scene: str = Field(..., min_length=1, description="开局场景文本")


class PresetCharacterAdminCreate(BaseModel):
    novel: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1)
    gender: Optional[str] = None
    age: Optional[int] = None
    rank: Optional[str] = None
    background: Optional[str] = None
    starting_points: int = Field(0, description="开局积分")
    timelines: List[TimelineEntrySchema] = Field(default_factory=list, description="该角色可玩的节点，整体替换")


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
