from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, GameSession, SceneHistory, ChoiceHistory
from app.schemas.schemas import (
    GameSessionCreate, GameSessionResponse, UserAction,
    Scene, GameStateResponse
)
from app.services.game_service import GameService
from typing import Optional
import uuid

router = APIRouter(prefix="/api/game", tags=["游戏"])


@router.post("/session", response_model=GameSessionResponse)
async def create_game_session(
    data: GameSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """创建游戏会话"""
    character = data.character

    # 如果是预设角色，获取完整信息
    character_info = None
    if character.character_type == "preset":
        character_info = GameService.get_preset_character(
            character.novel,
            character.name,
            character.timeline
        )
        if not character_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="预设角色不存在"
            )

    # 创建游戏会话
    game_session = GameSession(
        user_id=current_user.id if current_user else None,
        session_id=None,  # 首次调用LLM时生成
        character_name=character.name,
        character_gender=character.gender,
        character_age=character.age,
        character_rank=character.rank,
        character_background=character.background,
        novel=character.novel,
        timeline=character.timeline,
        character_type=character.character_type,
        points=character.starting_points,
        achievements=[]
    )

    # 创建初始场景
    if character.character_type == "preset" and character_info:
        initial_scene = {
            "scene_description": character_info['initial_scene_desc'],
            "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境", "随缘", "寻找穿越的原因"],
            "game_update": {"points_awarded": 0, "new_achievement": f"成为{character.name}"}
        }
        game_session.achievements.append(f"成为{character.name}")
    else:
        initial_scene = {
            "scene_description": f"你穿越到了{character.novel}的{character.timeline}时期，成为了{character.rank}。你需要决定下一步的行动",
            "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境", "随缘", "寻找穿越的原因"],
            "game_update": {"points_awarded": 0, "new_achievement": "穿越开始"}
        }
        game_session.achievements.append("穿越开始")

    game_session.current_scene = initial_scene

    # 保存到数据库
    db.add(game_session)
    await db.commit()
    await db.refresh(game_session)

    # 保存场景历史
    scene_history = SceneHistory(
        game_session_id=game_session.id,
        scene_description=initial_scene['scene_description'],
        choices=initial_scene['choices'],
        points_awarded=initial_scene['game_update']['points_awarded'],
        achievement=initial_scene['game_update']['new_achievement']
    )
    db.add(scene_history)
    await db.commit()

    return game_session


@router.post("/action", response_model=Scene)
async def perform_action(
    action_data: UserAction,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """执行游戏行动"""
    # 获取游戏会话
    result = await db.execute(
        select(GameSession).where(GameSession.id == action_data.game_session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在"
        )

    # 验证会话所有权（如果用户已登录）
    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此游戏会话"
        )

    # 准备角色信息
    character_info = {
        'name': game_session.character_name,
        'rank': game_session.character_rank,
        'background': game_session.character_background,
        'novel': game_session.novel,
        'timeline': game_session.timeline
    }

    # 如果是预设角色，获取动态背景
    if game_session.character_type == "preset":
        preset_info = GameService.get_preset_character(
            game_session.novel,
            game_session.character_name,
            game_session.timeline
        )
        if preset_info:
            character_info['dynamic_background'] = preset_info.get('dynamic_background')

    # 调用LLM
    raw_response, new_session_id = await GameService.call_llm_api(
        action_data.action,
        character_info,
        game_session.session_id
    )

    # 更新session_id
    if new_session_id:
        game_session.session_id = new_session_id

    # 解析响应
    new_scene = None
    if raw_response:
        new_scene = GameService.parse_llm_response(raw_response)

    if not new_scene:
        new_scene = GameService.get_fallback_scene(action_data.action)

    # 更新游戏状态
    game_session.points += new_scene['game_update']['points_awarded']
    new_achievement = new_scene['game_update']['new_achievement']
    if new_achievement and new_achievement not in game_session.achievements:
        achievements_list = list(game_session.achievements) if game_session.achievements else []
        achievements_list.append(new_achievement)
        game_session.achievements = achievements_list

    game_session.current_scene = new_scene

    # 保存场景历史
    scene_history = SceneHistory(
        game_session_id=game_session.id,
        scene_description=new_scene['scene_description'],
        choices=new_scene['choices'],
        points_awarded=new_scene['game_update']['points_awarded'],
        achievement=new_achievement
    )
    db.add(scene_history)

    # 保存选择历史
    choice_history = ChoiceHistory(
        game_session_id=game_session.id,
        choice=action_data.action,
        points=new_scene['game_update']['points_awarded']
    )
    db.add(choice_history)

    await db.commit()
    await db.refresh(game_session)

    return Scene(**new_scene)


@router.get("/session/{session_id}", response_model=GameSessionResponse)
async def get_game_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """获取游戏会话"""
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在"
        )

    # 验证会话所有权
    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此游戏会话"
        )

    return game_session


@router.get("/session/{session_id}/state", response_model=GameStateResponse)
async def get_game_state(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """获取游戏状态"""
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在"
        )

    # 统计场景和选择数量
    scene_count_result = await db.execute(
        select(func.count(SceneHistory.id)).where(SceneHistory.game_session_id == session_id)
    )
    scene_count = scene_count_result.scalar()

    choice_count_result = await db.execute(
        select(func.count(ChoiceHistory.id)).where(ChoiceHistory.game_session_id == session_id)
    )
    choice_count = choice_count_result.scalar()

    return GameStateResponse(
        points=game_session.points,
        achievements=game_session.achievements or [],
        scene_count=scene_count,
        choice_count=choice_count,
        current_scene=game_session.current_scene
    )
