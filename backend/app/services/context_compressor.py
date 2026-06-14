"""上下文压缩模块

当对话轮数超过阈值时，将旧轮压缩为一段故事概要，
通过 DeepSeek API 做摘要，后台执行不阻塞游戏响应。

同时提取结构化的角色追踪数据，持久化到 JSON 字段。
"""
import json
import re
import logging
from typing import Optional, List, Dict
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger("context_compressor")

SUMMARY_SYSTEM_PROMPT = (
    "你是一个专业的故事摘要助手，擅长从长文本中提取关键剧情信息"
    "并生成简洁连贯的概要。只输出概要文本，不要包含任何其他内容。"
)


def build_summary_prompt(
    existing_summary: Optional[str],
    turns: List[Dict],
) -> str:
    """构建摘要 prompt

    Args:
        existing_summary: 已有的故事概要（首次压缩时为 None）
        turns: 待压缩的对话轮次 [{"role": ..., "content": ...}, ...]

    Returns:
        摘要 prompt 字符串
    """
    # 将待压缩的轮次序列化为文本
    history_parts = []
    for msg in turns:
        role = msg["role"]
        content = msg["content"]
        if role == "assistant":
            history_parts.append(f"【场景】{content}")
        elif role == "user":
            history_parts.append(f"【玩家选择】{content}")

    history_text = "\n\n".join(history_parts)

    if existing_summary:
        return (
            "你是一个故事摘要助手。以下是一段已有的故事概要和新增的剧情。"
            "请将新内容整合到概要中，形成一段连贯的概要（400-900字）。\n\n"
            "**必须包含以下内容，缺一不可：**\n"
            "- 剧情演进：将新增剧情中的重要事件和转折合并到已有概要中\n"
            "- 关键人物清单：列出截至目前故事中**所有出现过的重要人物**，"
            "包括姓名、身份、与玩家的关系、当前状态（存活/死亡/离开/敌对/同盟等）。"
            "新增剧情中出现的新人物必须追加到此清单，旧人物不得删除。\n"
            "- 玩家当前处境与目标\n\n"
            f"已有概要：\n{existing_summary}\n\n"
            f"新增剧情：\n{history_text}\n\n"
            "请仅输出更新后的概要文本。"
        )
    else:
        return (
            "你是一个故事摘要助手。请将以下互动历史小说游戏的对话历史"
            "压缩为一段简洁的故事概要（400-600字），必须包含以下三个部分：\n\n"
            "1. **剧情概要**：重要的剧情事件、转折点，以及角色做出的关键选择及其后果。\n\n"
            "2. **关键人物清单**：列出对话历史中**所有出现过的重要人物**，"
            "每人一行，包含姓名、身份、与玩家的关系、当前状态。"
            "不要遗漏任何一个有名有姓或与玩家有过对话的角色。\n\n"
            "3. **当前处境**：玩家目前所处的位置、面临的选择和短期目标。\n\n"
            f"对话历史（格式为场景描述与玩家选择交替）：\n\n{history_text}\n\n"
            "请仅输出概要文本，严格包含以上三个部分。"
        )


async def call_summarization(prompt: str) -> Optional[str]:
    """调用 DeepSeek API 进行摘要

    使用非流式调用，低温度以确保事实准确性。
    失败时返回 None，由调用方决定重试策略。
    """
    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
            stream=False,
        )

        summary = response.choices[0].message.content
        if summary:
            summary = summary.strip()
            logger.info("SUMMARIZE_OK: chars=%d", len(summary))
            return summary
        else:
            logger.warning("SUMMARIZE_EMPTY: response content was empty")
            return None

    except Exception as e:
        logger.exception("SUMMARIZE_ERROR: %s", e)
        return None


# ── 角色提取 ─────────────────────────────────────────────────

CHARACTER_EXTRACTION_SYSTEM_PROMPT = (
    "你是一个专业的角色信息提取助手。"
    "根据提供的游戏故事概要，提取所有有名有姓的重要角色信息，"
    "以严格的 JSON 数组格式输出，不要包含任何额外内容。"
)


def build_character_extraction_prompt(
    summary_text: str,
    existing_characters: Optional[List[Dict]] = None,
) -> str:
    """构建角色提取 prompt

    将已有的角色列表与新概要一起发给 LLM，增量合并更新。

    Args:
        summary_text: 最新的故事概要文本
        existing_characters: 已有的角色列表 [{"name": ..., ...}, ...]
    """
    existing_json = (
        json.dumps(existing_characters, ensure_ascii=False, indent=2)
        if existing_characters else "[]"
    )

    return (
        "请从以下故事概要中提取所有出现过的重要角色信息。\n\n"
        "对每个角色，需提取以下字段：\n"
        "- name: 角色姓名（必填）\n"
        "- identity: 身份/职位\n"
        "- relationship_to_player: 与玩家的关系（如：主公、敌人、盟友、中立、手下、朋友等）\n"
        "- favorability: 好感度（-100到100的整数，根据剧情推断，不确定则填0）\n"
        "- status: 状态（存活/死亡/离开/敌对/同盟）\n"
        "- last_interaction: 最近一次与该角色互动的简述\n"
        "- first_appeared_turn: 无需填写，保持 null\n\n"
        "=== 已有角色（请在此基础上更新，不要删除已有角色）：===\n"
        f"{existing_json}\n\n"
        "=== 故事概要：===\n"
        f"{summary_text}\n\n"
        "**重要规则：**\n"
        "1. 已有角色列表中的人物必须全部保留，只更新状态、好感度等有变化的字段\n"
        "2. 新出现的角色必须追加到列表中\n"
        "3. 好感度推断规则：友好互动 +5~20，敌对/冲突 -5~20，重大背叛 -30~50\n"
        "4. 只输出纯 JSON 数组，格式：\n"
        '[{"name":"...","identity":"...","relationship_to_player":"...","favorability":0,"status":"存活","last_interaction":"...","first_appeared_turn":null}]'
    )


async def extract_characters(
    summary_text: str,
    existing_state: Optional[Dict] = None,
) -> Optional[Dict]:
    """从故事概要中提取结构化角色数据

    使用独立的低成本 LLM 调用，失败时返回 None，由调用方决定重试。

    Args:
        summary_text: 最新的完整故事概要文本
        existing_state: 已有的角色状态 {"characters": [...], "last_updated_turn": N}

    Returns:
        更新后的角色状态 dict，或 None（提取失败时）
    """
    existing_chars = (existing_state or {}).get("characters", [])
    last_turn = (existing_state or {}).get("last_updated_turn", 0)

    prompt = build_character_extraction_prompt(summary_text, existing_chars)

    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )

        response = client.chat.completions.create(
            model=settings.CHARACTER_EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": CHARACTER_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.CHARACTER_EXTRACTION_TEMPERATURE,
            max_tokens=1024,
            stream=False,
        )

        raw = (response.choices[0].message.content or "").strip()
        result = _parse_character_json(raw)

        if result and isinstance(result, list):
            return {
                "characters": result,
                "last_updated_turn": last_turn,
            }
        else:
            logger.warning(
                "CHARACTER_EXTRACT_PARSE_FAIL: chars=%d raw_preview=%.200s",
                len(raw), raw,
            )
            return None

    except Exception as e:
        logger.exception("CHARACTER_EXTRACT_ERROR: %s", e)
        return None


def _parse_character_json(raw_text: str) -> Optional[List]:
    """多级 fallback 解析 LLM 输出的角色 JSON 数组

    策略与 DeepSeekProvider._parse_choices 一致：
    去围栏 → 正则提取 → json.loads → ast.literal_eval
    """
    import ast

    text = raw_text.strip()
    # 去掉 markdown 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # 正则提取最外层 [...]
    m = re.search(r"\[.*\]", text, re.DOTALL)
    bracketed = m.group(0) if m else text

    # json.loads
    try:
        result = json.loads(bracketed)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # ast.literal_eval 兜底
    try:
        result = ast.literal_eval(bracketed)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        pass

    return None
