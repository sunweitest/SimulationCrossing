import re
import time
import json
import logging
from datetime import datetime
from pathlib import Path
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

# LLM 原始响应日志文件
_LLM_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LLM_LOG_DIR.mkdir(exist_ok=True)


def _log_llm_response(raw_text: str, session_id: int, success: bool) -> None:
    """将 LLM 原始响应写入日志文件，便于排查解析问题"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    status = "ok" if success else "err"
    filename = _LLM_LOG_DIR / f"llm_{ts}_{status}_session{session_id}.txt"
    try:
        filename.write_text(raw_text, encoding="utf-8")
        logger.info("LLM_LOG: 原始响应已写入 %s (%d chars)", filename.name, len(raw_text))
    except Exception as e:
        logger.warning("LLM_LOG: 写入失败 %s", e)


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


def _favorability_label(score: int) -> str:
    """将好感度数值转换为中文标签"""
    if score >= 80:
        return "深厚信任"
    elif score >= 50:
        return "友善"
    elif score >= 20:
        return "略有好感"
    elif score > -20:
        return "中立"
    elif score > -50:
        return "冷淡/不满"
    elif score > -80:
        return "敌视"
    else:
        return "深仇大恨"


def _prefilter_characters(
    user_input: str,
    characters_state: Optional[Dict],
    scene_text: str = "",
) -> list[Dict]:
    """扫描用户输入（及可选场景文本），匹配 characters_state 中的角色名。

    只返回用户提及的角色，避免全量注入浪费 token。
    匹配策略：简单子串匹配（角色名出现在输入文本中即命中）。
    """
    if not characters_state:
        return []
    chars = characters_state.get("characters", [])
    if not chars:
        return []

    combined = user_input + (" " + scene_text if scene_text else "")
    matched = []
    for c in chars:
        name = c.get("name", "")
        if name and name in combined:
            matched.append(c)
    return matched


def _build_character_context(matched_characters: list[Dict]) -> str:
    """将命中的角色列表格式化为注入到用户消息中的角色信息块"""
    if not matched_characters:
        return ""

    lines = []
    for c in matched_characters:
        fav = c.get("favorability", 0)
        label = _favorability_label(fav)
        lines.append(
            f"- {c['name']}（{c.get('identity', '未知')}）："
            f"与你的关系为「{c.get('relationship_to_player', '未知')}」"
            f"、好感度 {fav}（{label}）"
            f"、状态 {c.get('status', '存活')}"
        )

    return (
        "\n\n【相关人物信息】以下是你当前提及或涉及的人物详情，"
        "请在剧情中保持其行为与关系、好感度一致：\n"
        + "\n".join(lines)
    )


async def _character_tool_handler(
    tool_name: str,
    arguments_json: str,
    *,
    characters_state: Optional[Dict],
) -> str:
    """Tool call 处理函数：根据 name 查询角色详情

    由 DeepSeek provider 的 tool loop 调用，返回 JSON 字符串。
    """
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "参数解析失败"}, ensure_ascii=False)

    name = args.get("name", "")
    if not name:
        return json.dumps({"error": "缺少 name 参数"}, ensure_ascii=False)

    if not characters_state:
        return json.dumps({"found": False, "message": "暂无角色追踪数据"}, ensure_ascii=False)

    chars = characters_state.get("characters", [])
    for c in chars:
        if c.get("name") == name:
            fav = c.get("favorability", 0)
            c_copy = dict(c)
            c_copy["favorability_label"] = _favorability_label(fav)
            return json.dumps({"found": True, "character": c_copy}, ensure_ascii=False)

    return json.dumps({"found": False, "message": f"未找到角色「{name}」"}, ensure_ascii=False)


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
            # 注：人物关系不再全量注入，改为按需预过滤 + tool calling
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
            extract_characters,
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

                    # ── 角色提取（独立于摘要，失败不影响摘要存储）──
                    try:
                        existing_state = session.characters_state
                        char_state = await extract_characters(
                            new_summary, existing_state
                        )
                        if char_state:
                            char_state["last_updated_turn"] = (
                                session.summary_turn_count
                            )
                            session.characters_state = char_state
                            logger.info(
                                "CHARACTERS_UPDATED: session=%d count=%d turn=%d",
                                game_session_id,
                                len(char_state.get("characters", [])),
                                char_state["last_updated_turn"],
                            )
                    except Exception as e:
                        logger.exception(
                            "CHARACTERS_EXTRACT_FAILED: session=%d err=%s",
                            game_session_id, e,
                        )
                    # ──────────────────────────────────────────

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
        characters_state: Optional[Dict] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """调用 LLM API 生成场景

        如果提供了 characters_state：
        - 预过滤用户输入中提及的角色，注入到消息中
        - 启用 tool calling，LLM 可主动查询未提及但需要引用的角色
        """
        t_start = time.time()
        provider = get_provider()

        # ── 预过滤：扫描用户输入中提及的角色 ──
        prefiltered_context = ""
        tools = None
        tool_handler = None

        if characters_state:
            matched = _prefilter_characters(user_input, characters_state)
            if matched:
                prefiltered_context = _build_character_context(matched)
                logger.info(
                    "CHAR_PREFILTER: matched=%d names=%s",
                    len(matched),
                    [c["name"] for c in matched],
                )

            # 创建 tool handler，让 LLM 可以主动查询任何角色
            cs = characters_state  # capture for closure
            tool_handler = lambda name, args: _character_tool_handler(
                name, args, characters_state=cs,
            )
            from app.services.llm.deepseek_provider import CHARACTER_TOOLS
            tools = CHARACTER_TOOLS

        # 将预过滤的角色信息拼入 user_input
        augmented_input = user_input + prefiltered_context

        result = await provider.generate(
            character_info,
            augmented_input,
            session_id,
            history=history,
            tools=tools,
            tool_handler=tool_handler,
        )
        t_elapsed = time.time() - t_start
        logger.info(
            "LLM_CALL: time=%.1fs provider=%s success=%s",
            t_elapsed,
            settings.LLM_PROVIDER,
            result[0] is not None,
        )
        return result

    @staticmethod
    async def stream_story_text(
        user_input: str,
        character_info: Dict,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ):
        """流式生成纯剧情文本。"""
        provider = get_provider()
        if hasattr(provider, "stream_story"):
            return await provider.stream_story(
                character_info,
                user_input,
                session_id,
                history=history,
            )

        raw_text, new_session_id = await provider.generate(
            character_info,
            user_input,
            session_id,
            history=history,
        )

        async def iterator():
            if raw_text:
                yield raw_text

        return iterator(), new_session_id

    @staticmethod
    async def generate_scene_metadata(
        scene_description: str,
        character_info: Dict,
        user_input: str,
    ) -> Dict:
        """根据剧情生成选项、积分和成就。"""
        provider = get_provider()
        if hasattr(provider, "generate_scene_metadata"):
            return await provider.generate_scene_metadata(
                scene_description,
                character_info,
                user_input,
            )

        choices = await provider.generate_choices(scene_description, character_info)
        return {
            "choices": choices,
            "game_update": {"points_awarded": 5, "new_achievement": ""},
        }

    @staticmethod
    def parse_llm_response(raw_text: str, game_session_id: int = 0) -> Optional[Dict]:
        """解析 LLM 返回的 JSON"""
        t_start = time.time()

        if not raw_text:
            logger.warning("PARSE: raw_text为空（None或空字符串）")
            return None

        # 始终保存原始响应到日志文件
        _log_llm_response(raw_text, game_session_id, success=False)

        # 若原始响应全是空白，记录 hex
        if raw_text.isspace():
            hex_preview = raw_text[:100].encode("utf-8").hex(" ")
            logger.warning(
                "PARSE: 原始响应全是空白字符 len=%d hex前100字节=%s",
                len(raw_text), hex_preview,
            )
            return None

        # 先尝试直接 json.loads 整个文本（LLM 按要求输出纯 JSON 时直接命中）
        try:
            result = json.loads(raw_text)
            if isinstance(result, dict) and 'scene_description' in result:
                logger.info("PARSE_DIRECT: 直接 json.loads 成功")
                return GameService._validate_and_fill_result(result, raw_text, game_session_id)
        except (json.JSONDecodeError, ValueError):
            pass

        # 正则提取最外层 {...}（兜底 LLM 输出含多余文字的情况）
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            logger.warning(
                "PARSE: 未找到JSON对象 len=%d 前100字符=%.100s 后100字符=%.100s",
                len(raw_text),
                raw_text[:100].replace("\n", "\\n"),
                raw_text[-100:].replace("\n", "\\n"),
            )
            return None

        json_str = json_match.group()

        # 预处理：只转义 JSON 字符串值内部的非法控制字符，不动 JSON 结构
        def _sanitize_json(s: str) -> str:
            def _escape_inner(m: re.Match) -> str:
                content = m.group(1)
                buf = []
                for ch in content:
                    cp = ord(ch)
                    if cp < 0x20:
                        if ch == '\n':
                            buf.append('\\n')
                        elif ch == '\r':
                            buf.append('\\r')
                        elif ch == '\t':
                            buf.append('\\t')
                        else:
                            buf.append(f'\\u{cp:04x}')
                    else:
                        buf.append(ch)
                return '"' + ''.join(buf) + '"'

            # 匹配 JSON 字符串值 "..."，处理内部转义
            return re.sub(r'"((?:[^"\\]|\\.)*)"', _escape_inner, s)

        json_str = _sanitize_json(json_str)

        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            t_elapsed = time.time() - t_start
            logger.exception(
                "PARSE_JSON_ERROR: time=%.3fs error=%s json前200字符=%s",
                t_elapsed, e, json_str[:200],
            )
            return None

        return GameService._validate_and_fill_result(result, raw_text, game_session_id)

    @staticmethod
    def _validate_and_fill_result(
        result: Dict,
        raw_text: str,
        game_session_id: int,
    ) -> Optional[Dict]:
        """校验并补齐 LLM JSON 响应的字段"""
        required = ['scene_description', 'choices', 'game_update']
        missing = [k for k in required if k not in result]
        if missing:
            logger.warning("PARSE: JSON缺少字段 missing=%s", missing)
            return None

        if not isinstance(result['choices'], list) or len(result['choices']) == 0:
            result['choices'] = ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]

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

        _log_llm_response(raw_text, game_session_id, success=True)

        logger.info(
            "PARSE_OK: scene=%.50s choices=%d points=%d chars=%d",
            result['scene_description'][:50],
            len(result['choices']),
            game_update.get('points_awarded', 0),
            len(raw_text),
        )
        return result

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
