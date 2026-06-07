import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import PresetCharacter, CharacterTimeline, SceneHistory, ChoiceHistory, GameSession
from app.services.llm.base import LLMProvider

logger = logging.getLogger("game_service")


def _get_provider() -> LLMProvider:
    """根据配置返回 LLM 提供者实例"""
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "deepseek":
        from app.services.llm.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider()
    else:
        from app.services.llm.dashscope_provider import DashScopeProvider
        return DashScopeProvider()


_provider: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = _get_provider()
    return _provider


@dataclass
class ConversationContext:
    """对话上下文，包含预组装的 messages 和压缩状态"""
    messages: List[Dict] = field(default_factory=list)
    total_turns: int = 0
    needs_compression: bool = False
    turns_for_compression: List[Dict] = field(default_factory=list)


class GameService:
    """游戏服务"""

    # ── 角色查询 ──────────────────────────────────────────

    @staticmethod
    async def get_available_characters(
        db: AsyncSession,
        novel: Optional[str] = None,
        timeline: Optional[str] = None,
    ) -> Dict:
        """获取可用角色列表，按小说和时间节点筛选"""
        result: Dict[str, Dict[str, List[str]]] = {}

        stmt = select(PresetCharacter).options(selectinload(PresetCharacter.timelines))
        if novel:
            stmt = stmt.where(PresetCharacter.novel == novel)
        stmt = stmt.order_by(PresetCharacter.novel, PresetCharacter.id)

        rows = await db.execute(stmt)
        characters = rows.scalars().all()

        for char in characters:
            n_name = char.novel
            if n_name not in result:
                result[n_name] = {}
            for tl in char.timelines:
                if timeline and tl.timeline != timeline:
                    continue
                result[n_name].setdefault(tl.timeline, []).append(char.name)

        return result

    @staticmethod
    async def get_preset_character(
        db: AsyncSession, novel: str, character_name: str, timeline: str
    ) -> Optional[Dict]:
        """获取预设角色信息"""
        stmt = (
            select(PresetCharacter)
            .options(selectinload(PresetCharacter.timelines))
            .where(PresetCharacter.novel == novel, PresetCharacter.name == character_name)
        )
        row = await db.execute(stmt)
        char = row.scalar_one_or_none()

        if not char:
            return None

        tl_match = None
        for tl in char.timelines:
            if tl.timeline == timeline:
                tl_match = tl
                break

        if not tl_match:
            return None

        return {
            "name": char.name,
            "gender": char.gender,
            "age": char.age,
            "rank": char.rank,
            "background": char.background,
            "starting_points": char.starting_points,
            "novel": char.novel,
            "timeline": timeline,
            "dynamic_background": tl_match.background,
            "initial_scene_desc": tl_match.initial_scene,
        }

    # ── 对话历史与上下文压缩 ──────────────────────────────

    @staticmethod
    async def build_conversation_history(
        db: AsyncSession,
        game_session_id: int,
    ) -> ConversationContext:
        """构建 LLM 对话上下文，含自动压缩逻辑

        返回 ConversationContext，包含：
        - messages: 可直接传给 LLM 的消息列表
        - needs_compression: 是否需要后台执行摘要
        - turns_for_compression: 待压缩的轮次
        """
        # 加载游戏会话（获取 summary 字段）
        session = await db.get(GameSession, game_session_id)
        if not session:
            logger.warning("HISTORY: 会话不存在 id=%d", game_session_id)
            return ConversationContext()

        running_summary = session.running_summary
        summary_turn_count = session.summary_turn_count or 0

        # 查询场景历史（按时间排序）
        scene_stmt = (
            select(SceneHistory)
            .where(SceneHistory.game_session_id == game_session_id)
            .order_by(SceneHistory.created_at.asc())
        )
        scene_result = await db.execute(scene_stmt)
        scenes = scene_result.scalars().all()

        # 查询选择历史
        choice_stmt = (
            select(ChoiceHistory)
            .where(ChoiceHistory.game_session_id == game_session_id)
            .order_by(ChoiceHistory.created_at.asc())
        )
        choice_result = await db.execute(choice_stmt)
        choices = choice_result.scalars().all()

        total_turns = len(scenes)

        # 构建无冗余的对话历史（不含【可选行动】列表）
        def _build_plain_history(scenes_slice, choices_slice) -> List[Dict]:
            history = []
            for i, sc in enumerate(scenes_slice):
                history.append({
                    "role": "assistant",
                    "content": sc.scene_description or "",
                })
                if i < len(choices_slice):
                    history.append({
                        "role": "user",
                        "content": f"我选择：「{choices_slice[i].choice}」",
                    })
            return history

        threshold = settings.CONTEXT_COMPRESSION_THRESHOLD
        recent = settings.CONTEXT_RECENT_TURNS

        if total_turns <= threshold:
            # 未达阈值：返回完整历史（截断到 max_history_turns）
            max_msgs = settings.DEEPSEEK_MAX_HISTORY_TURNS * 2
            full_history = _build_plain_history(scenes, choices)
            return ConversationContext(
                messages=full_history[-max_msgs:],
                total_turns=total_turns,
            )

        # 已达阈值：组装"前情提要 + 最近 N 轮"
        old_turns_end = total_turns - recent
        recent_scenes = scenes[-recent:]
        recent_choices = choices[-recent:]
        recent_messages = _build_plain_history(recent_scenes, recent_choices)

        if running_summary:
            # 有摘要：前缀 + 最近轮
            prefix = [
                {
                    "role": "user",
                    "content": (
                        "【前情提要】以下是之前发生的主要事件的概要，"
                        "请记住这些信息以保持故事连贯性：\n\n"
                        f"{running_summary}"
                    ),
                },
                {
                    "role": "assistant",
                    "content": "我已了解之前的故事背景，会保持情节的连贯性。",
                },
            ]
            messages = prefix + recent_messages
        else:
            # 首次压缩但摘要还没生成：用 max_history_turns 兜底
            max_msgs = settings.DEEPSEEK_MAX_HISTORY_TURNS * 2
            full_history = _build_plain_history(scenes, choices)
            messages = full_history[-max_msgs:]

        # 判断是否需要触发后台压缩
        needs_compression = summary_turn_count < old_turns_end
        turns_for_compression = []
        if needs_compression:
            # 提取摘要未覆盖的旧轮
            new_start = summary_turn_count
            turns_for_compression = _build_plain_history(
                scenes[new_start:old_turns_end],
                choices[new_start:old_turns_end],
            )

        logger.info(
            "HISTORY: total_turns=%d summary_turns=%d messages=%d needs_compression=%s compress_turns=%d",
            total_turns,
            summary_turn_count,
            len(messages),
            needs_compression,
            len(turns_for_compression),
        )

        return ConversationContext(
            messages=messages,
            total_turns=total_turns,
            needs_compression=needs_compression,
            turns_for_compression=turns_for_compression,
        )

    @staticmethod
    async def compress_and_store_context(
        game_session_id: int,
        turns_to_compress: List[Dict],
        total_turns: int,
    ) -> None:
        """后台任务：压缩旧对话并存入数据库

        使用独立的 DB 会话，在 HTTP 响应之后执行。
        失败时静默返回，下次请求会自动重试。
        """
        from app.services.context_compressor import (
            build_summary_prompt,
            call_summarization,
        )

        try:
            async with AsyncSessionLocal() as db:
                session = await db.get(GameSession, game_session_id)
                if not session:
                    logger.error("COMPRESS: session not found id=%d", game_session_id)
                    return

                existing_summary = session.running_summary
                prompt = build_summary_prompt(existing_summary, turns_to_compress)
                new_summary = await call_summarization(prompt)

                if new_summary:
                    session.running_summary = new_summary
                    session.summary_turn_count = (
                        total_turns - settings.CONTEXT_RECENT_TURNS
                    )
                    await db.commit()
                    logger.info(
                        "COMPRESS_OK: session=%d turns_compressed=%d summary_chars=%d",
                        game_session_id,
                        len(turns_to_compress),
                        len(new_summary),
                    )
                else:
                    logger.warning(
                        "COMPRESS_FAIL: summarization returned empty, will retry next turn"
                    )

        except Exception as e:
            logger.exception("COMPRESS_ERROR: session=%d error=%s", game_session_id, e)

    # ── LLM 调用 ──────────────────────────────────────────

    @staticmethod
    async def call_llm_api(
        user_input: str,
        character_info: Dict,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """调用 LLM API 生成场景"""
        provider = get_provider()
        return await provider.generate(
            character_info,
            user_input,
            session_id,
            history=history,
        )

    @staticmethod
    def parse_llm_response(raw_text: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON"""
        if not raw_text:
            logger.warning("PARSE: raw_text为空")
            return None

        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            logger.warning("PARSE: 未找到JSON对象 raw_text前100字符=%s", raw_text[:100])
            return None

        json_str = json_match.group()
        try:
            result = json.loads(json_str)
            required = ['scene_description', 'choices', 'game_update']
            missing = [k for k in required if k not in result]
            if missing:
                logger.warning("PARSE: JSON缺少字段 missing=%s json=%s", missing, json_str[:200])
                return None

            if not isinstance(result['choices'], list) or len(result['choices']) == 0:
                result['choices'] = ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]

            # 确保恰好 5 个选项
            if len(result['choices']) < 5:
                defaults = ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]
                for d in defaults:
                    if len(result['choices']) >= 5:
                        break
                    if d not in result['choices']:
                        result['choices'].append(d)

            game_update = result.setdefault('game_update', {})
            game_update.setdefault('points_awarded', 5)
            game_update.setdefault('new_achievement', "")

            logger.info(
                "PARSE_OK: scene=%s choices=%d points=%d",
                result['scene_description'][:50],
                len(result['choices']),
                game_update.get('points_awarded', 0),
            )
            return result
        except json.JSONDecodeError as e:
            logger.exception("PARSE_JSON_ERROR: %s json_str前200字符=%s", e, json_str[:200])
            return None
        except Exception as e:
            logger.exception("PARSE_UNEXPECTED: %s", e)
            return None

    @staticmethod
    def get_fallback_scene(user_action: str) -> Dict:
        """获取备用场景（LLM 调用失败时使用）"""
        logger.info("FALLBACK: 使用备用场景 action=%s", user_action)
        return {
            "scene_description": (
                f"风云突变！你刚刚选择了「{user_action}」，"
                f"四周的气氛骤然紧张起来。远处传来隐约的马蹄声，"
                f"像是有什么大事即将发生。你深吸一口气，绷紧了神经。"
            ),
            "choices": ["拔剑应对", "冷静观察", "高声质问", "悄然退后", "寻求盟友"],
            "game_update": {"points_awarded": 7, "new_achievement": "随机应变"},
        }
