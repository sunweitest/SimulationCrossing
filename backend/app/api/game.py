import asyncio
import time
import logging
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_active_user
from app.models.models import User, GameSession, SceneHistory, ChoiceHistory, NovelConfig, TimelineConfig
from app.schemas.schemas import (
    GameSessionCreate, GameSessionResponse, UserAction,
    Scene, GameStateResponse, GameSessionListItem,
    CharacterInfoResponse, CharacterEntry, NovelTimelineResponse,
)
from sqlalchemy.orm import selectinload
from app.services.game_service import GameService, get_provider
from app.services.scene_image_matcher import get_matcher
from typing import Optional

logger = logging.getLogger("game_api")

router = APIRouter(prefix="/api/game", tags=["游戏"])


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/characters")
async def get_available_characters(
    novel: Optional[str] = None,
    timeline: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取可用预设角色列表，可按小说和时间节点筛选"""
    return await GameService.get_available_characters(db, novel=novel, timeline=timeline)


@router.get("/novels", response_model=list[NovelTimelineResponse])
async def get_novels(db: AsyncSession = Depends(get_db)):
    """获取所有小说背景及其时间节点（公开接口，供角色创建页使用）"""
    result = await db.execute(
        select(NovelConfig)
        .options(selectinload(NovelConfig.timelines))
        .order_by(NovelConfig.sort_order, NovelConfig.id)
    )
    novels = result.scalars().all()
    return [
        NovelTimelineResponse(
            novel_id=n.id,
            novel_name=n.name,
            description=n.description,
            timelines=[t.name for t in sorted(n.timelines, key=lambda x: x.sort_order)],
        )
        for n in novels
    ]


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
        character_info = await GameService.get_preset_character(db,
            character.novel,
            character.name,
            character.timeline
        )
        if not character_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="预设角色不存在"
            )

    session_character = {
        "name": character.name,
        "gender": character.gender,
        "age": character.age,
        "rank": character.rank,
        "background": character.background,
        "starting_points": character.starting_points
    }
    if character_info:
        session_character.update({
            "name": character_info["name"],
            "gender": character_info["gender"],
            "age": character_info["age"],
            "rank": character_info["rank"],
            "background": character_info["background"],
            "starting_points": character_info.get("starting_points", character.starting_points)
        })

    # 创建游戏会话
    game_session = GameSession(
        user_id=current_user.id if current_user else None,
        session_id=None,  # 首次调用LLM时生成
        character_name=session_character["name"],
        character_gender=session_character["gender"],
        character_age=session_character["age"],
        character_rank=session_character["rank"],
        character_background=session_character["background"],
        novel=character.novel,
        timeline=character.timeline,
        character_type=character.character_type,
        points=session_character["starting_points"],
        achievements=[]
    )

    # 创建初始场景
    if character.character_type == "preset" and character_info:
        initial_scene = {
            "scene_description": character_info['initial_scene_desc'],
            "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境", "随缘", "寻找穿越的原因"],
            "game_update": {"points_awarded": 0, "new_achievement": f"成为{session_character['name']}"}
        }
        game_session.achievements.append(f"成为{session_character['name']}")
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """执行游戏行动"""
    t_total_start = time.time()
    logger.info("ACTION_START: session_id=%d action=%.40s user=%s",
                action_data.game_session_id, action_data.action,
                current_user.id if current_user else "guest")

    # 获取游戏会话
    result = await db.execute(
        select(GameSession).where(GameSession.id == action_data.game_session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        logger.warning("ACTION: 会话不存在 session_id=%d", action_data.game_session_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在"
        )

    # 验证会话所有权（如果用户已登录）
    if current_user and game_session.user_id != current_user.id:
        logger.warning("ACTION: 权限拒绝 session_id=%d owner=%s requester=%s",
                       action_data.game_session_id, game_session.user_id, current_user.id)
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
        preset_info = await GameService.get_preset_character(db,
            game_session.novel,
            game_session.character_name,
            game_session.timeline
        )
        if preset_info:
            character_info['dynamic_background'] = preset_info.get('dynamic_background')
        else:
            logger.warning("ACTION: 预设角色信息未找到 novel=%s name=%s timeline=%s",
                           game_session.novel, game_session.character_name, game_session.timeline)

    # 构建对话上下文（含自动压缩逻辑）
    context = await GameService.build_conversation_history(
        db,
        action_data.game_session_id,
    )

    # 调度后台上下文压缩
    if context.needs_compression and context.turns_for_compression:
        background_tasks.add_task(
            GameService.compress_and_store_context,
            action_data.game_session_id,
            context.turns_for_compression,
            context.total_turns,
        )

    # 调用LLM（使用预组装的 messages，启用按需角色查询）
    raw_response, new_session_id = await GameService.call_llm_api(
        action_data.action,
        character_info,
        game_session.session_id,
        history=context.messages,
        characters_state=game_session.characters_state,
    )

    # 更新session_id
    if new_session_id:
        logger.info("ACTION: session_id更新 old=%s new=%s", game_session.session_id, new_session_id)
        game_session.session_id = new_session_id

    # 解析响应
    new_scene = None
    if raw_response:
        new_scene = GameService.parse_llm_response(raw_response, game_session_id=action_data.game_session_id)

    # 智能降级：JSON 解析失败但有有效文本 → 用 AI 文本作场景描述 + LLM 生成选项
    if not new_scene and raw_response:
        text = raw_response.strip()
        if text and not text.isspace():
            logger.info(
                "ACTION_SMART_FALLBACK: JSON解析失败 session=%d action=%.40s text_len=%d",
                action_data.game_session_id,
                action_data.action,
                len(text),
            )
            desc = text[:6000]  # 匹配 LLM 典型输出长度
            # 轻量调用 LLM 生成贴合场景的选项
            provider = get_provider()
            choices = await provider.generate_choices(desc, character_info)
            new_scene = {
                "scene_description": desc,
                "choices": choices,
                "game_update": {"points_awarded": 5, "new_achievement": ""},
            }

    # 最终兜底：完全没有有效响应
    if not new_scene:
        logger.warning(
            "ACTION_HARD_FALLBACK: session=%d action=%.40s raw_is_none=%s raw_len=%d",
            action_data.game_session_id,
            action_data.action,
            raw_response is None,
            len(raw_response) if raw_response else 0,
        )
        new_scene = GameService.get_fallback_scene(action_data.action)

    # 场景图片匹配（非流式端点，与 DB 更新串行即可）
    if new_scene and new_scene.get("scene_description"):
        matcher = get_matcher()
        if matcher and matcher.is_ready:
            try:
                new_scene["scene_image"] = await matcher.find_best_match(
                    new_scene["scene_description"]
                )
            except Exception as e:
                logger.warning("ACTION: 图片匹配失败（非致命）: %s", e)
                new_scene["scene_image"] = None
        else:
            new_scene["scene_image"] = None
    else:
        new_scene["scene_image"] = None

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

    t_total = time.time() - t_total_start
    logger.info(
        "ACTION_DONE: session_id=%d action=%.30s time=%.1fs points=%d achievements=%d",
        action_data.game_session_id,
        action_data.action,
        t_total,
        game_session.points,
        len(game_session.achievements) if game_session.achievements else 0,
    )

    return Scene(**new_scene)


@router.post("/action/stream")
async def perform_action_stream(
    action_data: UserAction,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """流式执行游戏行动：先推送纯剧情，再推送选项/积分/成就。"""
    t_total_start = time.time()
    logger.info(
        "ACTION_STREAM_START: session_id=%d action=%.40s user=%s",
        action_data.game_session_id,
        action_data.action,
        current_user.id if current_user else "guest",
    )

    result = await db.execute(
        select(GameSession).where(GameSession.id == action_data.game_session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在",
        )

    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此游戏会话",
        )

    character_info = {
        "name": game_session.character_name,
        "rank": game_session.character_rank,
        "background": game_session.character_background,
        "novel": game_session.novel,
        "timeline": game_session.timeline,
    }

    if game_session.character_type == "preset":
        preset_info = await GameService.get_preset_character(
            db,
            game_session.novel,
            game_session.character_name,
            game_session.timeline,
        )
        if preset_info:
            character_info["dynamic_background"] = preset_info.get("dynamic_background")

    context = await GameService.build_conversation_history(
        db,
        action_data.game_session_id,
    )

    if context.needs_compression and context.turns_for_compression:
        background_tasks.add_task(
            GameService.compress_and_store_context,
            action_data.game_session_id,
            context.turns_for_compression,
            context.total_turns,
        )

    async def event_stream():
        story_parts = []

        # 重新查询 game_session，确保在异步生成器内附着在当前 session 上
        result = await db.execute(
            select(GameSession).where(GameSession.id == action_data.game_session_id)
        )
        game_session_local = result.scalar_one_or_none()
        if not game_session_local:
            yield _sse("error", {"message": "游戏会话已丢失"})
            return

        new_session_id = game_session_local.session_id

        yield _sse("status", {"phase": "story", "message": "剧情生成中"})

        try:
            story_iter, generated_session_id = await GameService.stream_story_text(
                action_data.action,
                character_info,
                game_session_local.session_id,
                history=context.messages,
                characters_state=game_session_local.characters_state,
            )
            new_session_id = generated_session_id or new_session_id

            async for chunk in story_iter:
                story_parts.append(chunk)
                yield _sse("story_chunk", {"delta": chunk})
        except Exception as exc:
            logger.exception("ACTION_STREAM_STORY_FAIL: %s", exc)
            fallback = GameService.get_fallback_scene(action_data.action)
            story_parts = [fallback["scene_description"]]
            yield _sse("story_chunk", {"delta": fallback["scene_description"]})

        scene_description = "".join(story_parts).strip()
        if not scene_description:
            fallback = GameService.get_fallback_scene(action_data.action)
            scene_description = fallback["scene_description"]
            yield _sse("story_chunk", {"delta": scene_description})

        yield _sse("status", {"phase": "metadata", "message": "行动选项生成中"})

        # 并行：场景元数据生成 + 图片匹配
        matcher = get_matcher()
        metadata_coro = GameService.generate_scene_metadata(
            scene_description,
            character_info,
            action_data.action,
        )
        image_coro = matcher.find_best_match(scene_description) if matcher and matcher.is_ready else None

        if image_coro:
            metadata, scene_image = await asyncio.gather(metadata_coro, image_coro)
        else:
            metadata = await metadata_coro
            scene_image = None

        new_scene = {
            "scene_description": scene_description,
            "choices": metadata["choices"],
            "game_update": metadata["game_update"],
            "scene_image": scene_image,
        }

        if new_session_id:
            game_session_local.session_id = new_session_id

        game_session_local.points += new_scene["game_update"]["points_awarded"]
        new_achievement = new_scene["game_update"]["new_achievement"]
        if new_achievement and new_achievement not in game_session_local.achievements:
            achievements_list = list(game_session_local.achievements) if game_session_local.achievements else []
            achievements_list.append(new_achievement)
            game_session_local.achievements = achievements_list

        game_session_local.current_scene = new_scene

        scene_history = SceneHistory(
            game_session_id=game_session_local.id,
            scene_description=new_scene["scene_description"],
            choices=new_scene["choices"],
            points_awarded=new_scene["game_update"]["points_awarded"],
            achievement=new_achievement,
        )
        db.add(scene_history)

        choice_history = ChoiceHistory(
            game_session_id=game_session_local.id,
            choice=action_data.action,
            points=new_scene["game_update"]["points_awarded"],
        )
        db.add(choice_history)

        await db.commit()
        await db.refresh(game_session_local)

        logger.info(
            "ACTION_STREAM_DONE: session_id=%d action=%.30s time=%.1fs points=%d achievements=%d",
            action_data.game_session_id,
            action_data.action,
            time.time() - t_total_start,
            game_session_local.points,
            len(game_session_local.achievements) if game_session_local.achievements else 0,
        )

        yield _sse("scene", new_scene)
        yield _sse("done", {"ok": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/character/{novel}/{name}")
async def get_character_detail(
    novel: str,
    name: str,
    timeline: str,
    db: AsyncSession = Depends(get_db)
):
    """获取预设角色详细信息"""
    char_info = await GameService.get_preset_character(db, novel, name, timeline)
    if not char_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在或该时间节点不适用"
        )
    return char_info


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


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除游戏会话"""
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在"
        )

    if game_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此游戏会话"
        )

    await db.delete(game_session)
    await db.commit()


@router.get("/sessions", response_model=list[GameSessionListItem])
async def list_game_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的所有游戏会话"""
    result = await db.execute(
        select(GameSession)
        .where(GameSession.user_id == current_user.id)
        .order_by(GameSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    return [
        GameSessionListItem(
            id=s.id,
            character_name=s.character_name,
            character_gender=s.character_gender,
            character_age=s.character_age,
            character_rank=s.character_rank,
            novel=s.novel,
            timeline=s.timeline,
            character_type=s.character_type,
            points=s.points,
            achievements=s.achievements or [],
            current_scene_desc=(
                s.current_scene["scene_description"][:80] + "..."
                if s.current_scene
                and isinstance(s.current_scene, dict)
                and s.current_scene.get("scene_description")
                else None
            ),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


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


# ── 角色追踪查询 ──────────────────────────────────────────

@router.get("/session/{session_id}/characters", response_model=CharacterInfoResponse)
async def get_session_characters(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取游戏会话中所有已追踪的角色及其好感度"""
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在",
        )

    state = game_session.characters_state or {}
    characters = state.get("characters", [])
    return CharacterInfoResponse(
        session_id=session_id,
        total_characters=len(characters),
        characters=[CharacterEntry(**c) for c in characters],
        last_updated_turn=state.get("last_updated_turn", 0),
    )


@router.get("/session/{session_id}/character/{character_name}")
async def get_session_character(
    session_id: int,
    character_name: str,
    db: AsyncSession = Depends(get_db),
):
    """按名字查询游戏会话中的特定角色"""
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    game_session = result.scalar_one_or_none()

    if not game_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏会话不存在",
        )

    state = game_session.characters_state or {}
    for char in state.get("characters", []):
        if char.get("name") == character_name:
            return CharacterEntry(**char)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"角色 '{character_name}' 未找到",
    )
