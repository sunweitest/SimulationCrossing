import asyncio
import time
import logging
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
import redis.asyncio as redis
from redis.exceptions import RedisError
from app.core.config import settings
from app.services.quota import get_quota_status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_active_user
from app.models.models import User, GameSession, SceneHistory, ChoiceHistory, NovelConfig, TimelineConfig
from app.schemas.schemas import (
    GameSessionCreate, GameSessionResponse, UserAction,
    Scene, GameStateResponse, GameSessionListItem,
    CharacterInfoResponse, CharacterEntry, NovelTimelineResponse, RewindRequest,
)
from sqlalchemy.orm import selectinload
from app.services.game_service import GameService, get_provider
from app.services.scene_image_matcher import get_matcher
from typing import Optional

logger = logging.getLogger("game_api")

router = APIRouter(prefix="/api/game", tags=["游戏"])


async def _claim_anonymous_session(db: AsyncSession, game_session: GameSession, current_user) -> None:
    """游客存档在登录后归到该用户名下。

    没有这一步，登录前创建的会话 user_id 仍是 NULL，登录后再操作会判成
    「无权访问」（403），用户看到的就是「登录后进度没保存」。
    """
    if current_user is None or game_session.user_id is not None:
        return
    game_session.user_id = current_user.id
    await db.commit()
    logger.info("SESSION_CLAIMED: session_id=%d new_owner=%d", game_session.id, current_user.id)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _next_turn_index(db: AsyncSession, session_id: int) -> int:
    """下一回合序号（0 = 开局，之后每次行动 +1）。"""
    result = await db.execute(
        select(func.max(SceneHistory.turn_index)).where(SceneHistory.game_session_id == session_id)
    )
    current_max = result.scalar()
    return 0 if current_max is None else current_max + 1


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


@router.get("/quota")
async def get_my_quota(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    """查询当前身份今天还能对话几次（游戏界面右上角展示用）

    未登录：每日 DAILY_FREE_MESSAGES 次，用完提示登录
    已登录：每日 DAILY_FREE_MESSAGES + DAILY_LOGGED_IN_EXTRA，另有额外配额/包月不限
    """
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
    try:
        return await get_quota_status(client, request, current_user)
    except RedisError as exc:
        logger.warning("QUOTA_UNAVAILABLE: %s", exc)
        # Redis 挂了不影响游戏，前端按“未知”处理
        return {
            "is_guest": current_user is None,
            "daily_limit": None,
            "used_today": 0,
            "daily_remaining": None,
            "extra_quota": 0,
            "is_unlimited": False,
            "remaining": None,
            "unavailable": True,
        }
    finally:
        await client.aclose()


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
    mission_def = (character_info or {}).get("mission")
    if not mission_def and character.character_type != "preset":
        # 自定义角色：按姓名/身份/背景现拟一条使命
        mission_def = await GameService.generate_custom_mission({
            "name": session_character["name"],
            "rank": session_character["rank"],
            "age": session_character["age"],
            "gender": session_character["gender"],
            "background": session_character.get("background") or "",
            "novel": character.novel,
            "timeline": character.timeline,
        })
    game_session.mission_state = GameService.init_mission_state(mission_def)

    # 创建初始场景
    if character.character_type == "preset" and character_info:
        initial_scene = {
            "scene_description": character_info['initial_scene_desc'],
            "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境"],
            "game_update": {"points_awarded": 0, "new_achievement": f"成为{session_character['name']}"}
        }
        game_session.achievements.append(f"成为{session_character['name']}")
    else:
        initial_scene = {
            "scene_description": f"你穿越到了{character.novel}的{character.timeline}时期，成为了{character.rank}。你需要决定下一步的行动",
            "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境"],
            "game_update": {"points_awarded": 0, "new_achievement": "穿越开始"}
        }
        game_session.achievements.append("穿越开始")

    initial_scene["mission"] = GameService.mission_public(game_session)
    game_session.current_scene = initial_scene

    # 保存到数据库
    db.add(game_session)
    await db.commit()
    await db.refresh(game_session)

    # 保存场景历史
    scene_history = SceneHistory(
        game_session_id=game_session.id,
        turn_index=0,
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
    await _claim_anonymous_session(db, game_session, current_user)
    if current_user and game_session.user_id != current_user.id:
        logger.warning("ACTION: 权限拒绝 session_id=%d owner=%s requester=%s",
                       action_data.game_session_id, game_session.user_id, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此游戏会话"
        )

    # 主角已死：这一局结束，不再接受行动
    if GameService.is_ended(game_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "这一局已经结束了。主角已经死了，去「我的游戏」开始新的一局吧。", "ended": True},
        )

    # 上一回合使命失败 → 本回合切到第二幕
    if GameService.enter_second_act(game_session):
        await db.commit()
        logger.info("MISSION_SECOND_ACT: session_id=%d", game_session.id)

    # 准备角色信息
    character_info = {
        'name': game_session.character_name,
        'rank': game_session.character_rank,
        'background': game_session.character_background,
        'novel': game_session.novel,
        'timeline': game_session.timeline,
        'mission_state': game_session.mission_state,
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
                    new_scene["scene_description"], novel=game_session.novel
                )
            except Exception as e:
                logger.warning("ACTION: 图片匹配失败（非致命）: %s", e)
                new_scene["scene_image"] = None
        else:
            new_scene["scene_image"] = None
    else:
        new_scene["scene_image"] = None

    # 使命判定（有使命才会多一次轻量调用）
    mission_res = {"points": 0, "achievements": [], "mission": None}
    if isinstance(game_session.mission_state, dict):
        try:
            judged = await GameService.judge_mission(
                new_scene["scene_description"], character_info, action_data.action
            )
            mission_res = GameService.apply_mission_update(game_session, judged)
        except Exception as e:
            logger.warning("MISSION_JUDGE_FAIL: session=%d %s", game_session.id, e)
            mission_res["mission"] = GameService.mission_public(game_session)
    new_scene["mission"] = mission_res["mission"]

    # 更新游戏状态（使命积分并入本回合得分，前端只加一次）
    if mission_res["points"]:
        new_scene["game_update"]["points_awarded"] += mission_res["points"]
    new_scene["mission_achievements"] = mission_res["achievements"]
    game_session.points += new_scene['game_update']['points_awarded']
    for _ach in mission_res["achievements"]:
        _list = list(game_session.achievements) if game_session.achievements else []
        if _ach not in _list:
            _list.append(_ach)
        game_session.achievements = _list
    new_achievement = new_scene['game_update']['new_achievement']
    if new_achievement and new_achievement not in game_session.achievements:
        achievements_list = list(game_session.achievements) if game_session.achievements else []
        achievements_list.append(new_achievement)
        game_session.achievements = achievements_list

    game_session.current_scene = new_scene

    # 保存场景历史
    turn_index = await _next_turn_index(db, game_session.id)
    scene_history = SceneHistory(
        game_session_id=game_session.id,
        turn_index=turn_index,
        scene_description=new_scene['scene_description'],
        choices=new_scene['choices'],
        points_awarded=new_scene['game_update']['points_awarded'],
        achievement=new_achievement,
        scene_image=new_scene.get('scene_image')
    )
    db.add(scene_history)

    # 保存选择历史
    choice_history = ChoiceHistory(
        game_session_id=game_session.id,
        turn_index=turn_index,
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

    await _claim_anonymous_session(db, game_session, current_user)
    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此游戏会话",
        )

    # 主角已死：终局，不再生成剧情
    if GameService.is_ended(game_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "这一局已经结束了。主角已经死了，去「我的游戏」开始新的一局吧。", "ended": True},
        )

    # 上一回合使命失败 → 本回合进入第二幕
    if GameService.enter_second_act(game_session):
        # 必须立刻落库：流式端点稍后会重新 SELECT 一次会话，不提交的话会读到旧的 failed
        await db.commit()
        logger.info("MISSION_SECOND_ACT_STREAM: session_id=%d", game_session.id)

    character_info = {
        "name": game_session.character_name,
        "rank": game_session.character_rank,
        "background": game_session.character_background,
        "novel": game_session.novel,
        "timeline": game_session.timeline,
        "mission_state": game_session.mission_state,
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
        mission_coro = (
            GameService.judge_mission(scene_description, character_info, action_data.action)
            if isinstance(game_session_local.mission_state, dict)
            else None
        )
        image_coro = (
            matcher.find_best_match(scene_description, novel=game_session_local.novel)
            if matcher and matcher.is_ready
            else None
        )

        if image_coro and mission_coro:
            metadata, scene_image, mission_update = await asyncio.gather(
                metadata_coro, image_coro, mission_coro
            )
        elif image_coro:
            metadata, scene_image = await asyncio.gather(metadata_coro, image_coro)
            mission_update = None
        elif mission_coro:
            metadata, mission_update = await asyncio.gather(metadata_coro, mission_coro)
            scene_image = None
        else:
            metadata = await metadata_coro
            scene_image = None
            mission_update = None

        new_scene = {
            "scene_description": scene_description,
            "choices": metadata["choices"],
            "game_update": metadata["game_update"],
            "scene_image": scene_image,
        }
        mission_res = GameService.apply_mission_update(
            game_session_local, mission_update or metadata.get("mission_update")
        )
        new_scene["mission"] = mission_res["mission"]
        if mission_res["points"]:
            new_scene["game_update"]["points_awarded"] += mission_res["points"]
        new_scene["mission_achievements"] = mission_res["achievements"]

        if new_session_id:
            game_session_local.session_id = new_session_id

        game_session_local.points += new_scene["game_update"]["points_awarded"]
        new_achievement = new_scene["game_update"]["new_achievement"]
        if new_achievement and new_achievement not in game_session_local.achievements:
            achievements_list = list(game_session_local.achievements) if game_session_local.achievements else []
            achievements_list.append(new_achievement)
            game_session_local.achievements = achievements_list

        for _ach in mission_res["achievements"]:
            _list = list(game_session_local.achievements) if game_session_local.achievements else []
            if _ach not in _list:
                _list.append(_ach)
            game_session_local.achievements = _list

        game_session_local.current_scene = new_scene

        turn_index = await _next_turn_index(db, game_session_local.id)
        scene_history = SceneHistory(
            game_session_id=game_session_local.id,
            turn_index=turn_index,
            scene_description=new_scene["scene_description"],
            choices=new_scene["choices"],
            points_awarded=new_scene["game_update"]["points_awarded"],
            achievement=new_achievement,
            scene_image=new_scene.get("scene_image"),
        )
        db.add(scene_history)

        choice_history = ChoiceHistory(
            game_session_id=game_session_local.id,
            turn_index=turn_index,
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
    await _claim_anonymous_session(db, game_session, current_user)
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

    await _claim_anonymous_session(db, game_session, current_user)
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


# ── 回合回溯 ────────────────────────────────────────────────────────────────

@router.get("/session/{session_id}/turns")
async def list_turns(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """列出该会话的所有回合，供「回溯」面板选择。"""
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    game_session = result.scalar_one_or_none()
    if not game_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="游戏会话不存在")

    await _claim_anonymous_session(db, game_session, current_user)
    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此游戏会话")

    scenes = (await db.execute(
        select(SceneHistory)
        .where(SceneHistory.game_session_id == session_id)
        .order_by(SceneHistory.turn_index.asc())
    )).scalars().all()
    choices = (await db.execute(
        select(ChoiceHistory).where(ChoiceHistory.game_session_id == session_id)
    )).scalars().all()
    choice_by_turn = {c.turn_index: c.choice for c in choices}
    latest_turn = scenes[-1].turn_index if scenes else 0

    items = []
    for sc in scenes:
        text = (sc.scene_description or "").replace("\n", " ").strip()
        items.append({
            "turn_index": sc.turn_index,
            "preview": text[:70] + ("…" if len(text) > 70 else ""),
            "choice": choice_by_turn.get(sc.turn_index),
            "points_awarded": sc.points_awarded or 0,
            "created_at": sc.created_at.isoformat() if sc.created_at else None,
            "is_current": sc.turn_index == latest_turn,
        })
    return items


@router.post("/session/{session_id}/rewind")
async def rewind_session(
    session_id: int,
    payload: RewindRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """回到第 payload.turn_index 回合：之后的回合记录会被删除。

    回溯不调用 LLM，因此不消耗次数。积分按被删回合的加分回退，
    成就按保留下来的回合重新汇总；摘要/人物状态清空，下次压缩时重建。
    """
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    game_session = result.scalar_one_or_none()
    if not game_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="游戏会话不存在")

    await _claim_anonymous_session(db, game_session, current_user)
    if current_user and game_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此游戏会话")

    scenes = (await db.execute(
        select(SceneHistory)
        .where(SceneHistory.game_session_id == session_id)
        .order_by(SceneHistory.turn_index.asc())
    )).scalars().all()
    if not scenes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该存档没有回合记录")

    target = payload.turn_index
    latest = scenes[-1].turn_index
    if target < 0 or target > latest:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="回合不存在")

    kept = [s for s in scenes if s.turn_index <= target]
    removed = [s for s in scenes if s.turn_index > target]
    if not removed:
        # 已经在目标回合，直接返回当前状态
        return {
            "turn_index": target,
            "removed_turns": 0,
            "current_scene": game_session.current_scene,
            "points": game_session.points,
            "achievements": game_session.achievements or [],
        }

    last_kept = kept[-1]
    removed_points = sum((s.points_awarded or 0) for s in removed)

    await db.execute(
        delete(ChoiceHistory).where(
            ChoiceHistory.game_session_id == session_id,
            ChoiceHistory.turn_index > target,
        )
    )
    await db.execute(
        delete(SceneHistory).where(
            SceneHistory.game_session_id == session_id,
            SceneHistory.turn_index > target,
        )
    )

    game_session.points = max(0, (game_session.points or 0) - removed_points)

    # 成就按保留下来的回合重新汇总（保持首次出现顺序、去重）
    rebuilt = []
    for sc in kept:
        name = (sc.achievement or "").strip()
        if name and name not in rebuilt:
            rebuilt.append(name)
    game_session.achievements = rebuilt

    # 使命：天数按保留回合重算；已走过的阶段不回退（视为既成事实）
    ms = game_session.mission_state
    if isinstance(ms, dict) and isinstance(ms.get("mission"), dict):
        ms = dict(ms)
        ms["turns_used"] = len(kept)
        ms["days_left"] = max(
            0,
            int(ms.get("deadline_turns") or 10) - len(kept) - int(ms.get("penalty") or 0),
        )
        if ms.get("status") == "failed" and ms["days_left"] > 0:
            ms["status"] = "active"
        ms["last_label"] = ""
        ms["last_note"] = ""
        game_session.mission_state = ms

    game_session.current_scene = {
        "scene_description": last_kept.scene_description,
        "choices": last_kept.choices or [],
        "game_update": {"points_awarded": 0, "new_achievement": ""},
        "scene_image": last_kept.scene_image,
        "mission": GameService.mission_public(game_session),
    }

    # 摘要与人物状态覆盖了被删除的回合，清空让下次压缩重建
    game_session.running_summary = None
    game_session.summary_turn_count = 0
    game_session.characters_state = None

    await db.commit()
    await db.refresh(game_session)

    logger.info(
        "REWIND: session_id=%d target_turn=%d removed=%d points=%d",
        session_id, target, len(removed), game_session.points,
    )

    return {
        "turn_index": target,
        "removed_turns": len(removed),
        "current_scene": game_session.current_scene,
        "points": game_session.points,
        "achievements": game_session.achievements or [],
    }
