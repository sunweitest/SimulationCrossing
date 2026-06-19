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
            max_tokens=4096,
            stream=False,
        )

        finish_reason = response.choices[0].finish_reason
        raw = (response.choices[0].message.content or "").strip()
        _save_character_raw_log(raw, last_turn)

        if finish_reason == "length":
            logger.warning(
                "CHARACTER_EXTRACT_TRUNCATED: max_tokens 不足，输出被截断 chars=%d",
                len(raw),
            )
            # 尝试修复截断的 JSON：补上缺失的引号和括号
            raw = _repair_truncated_json(raw)

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


def _save_character_raw_log(raw_text: str, last_turn: int) -> None:
    """将角色提取的原始 LLM 响应写入日志文件，方便排查解析失败"""
    try:
        from pathlib import Path
        from datetime import datetime
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = log_dir / f"character_raw_{ts}_turn{last_turn}.txt"
        fname.write_text(raw_text, encoding="utf-8")
        logger.info("CHARACTER_RAW_LOG: %s", fname.name)
    except Exception as e:
        logger.warning("CHARACTER_RAW_LOG_ERR: %s", e)


def _parse_character_json(raw_text: str) -> Optional[List]:
    """多级 fallback 解析 LLM 输出的角色 JSON 数组

    策略：
    1. 去围栏 → 控制字符清理 → 正则提取 → json.loads → ast.literal_eval
    2. 兜底：尝试从 {"characters": [...]} 对象中提取
    """
    import ast

    text = raw_text.strip()
    # 去掉 markdown 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # ── 尝试作为对象提取 {"characters": [...]} ──
    for candidate in _extract_candidates(text):
        # json.loads
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # 控制字符清理后重试
        sanitized = _sanitize_json_string(candidate)
        try:
            result = json.loads(sanitized)
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # ast.literal_eval 兜底
        try:
            result = ast.literal_eval(candidate)
            if isinstance(result, list):
                return result
        except (ValueError, SyntaxError):
            pass

        try:
            result = ast.literal_eval(sanitized)
            if isinstance(result, list):
                return result
        except (ValueError, SyntaxError):
            pass

    # ── 兜底：尝试解析 {"characters": [...]} 对象 ──
    try:
        result = json.loads(text)
        if isinstance(result, dict) and "characters" in result:
            return result["characters"]
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        result = json.loads(_sanitize_json_string(text))
        if isinstance(result, dict) and "characters" in result:
            return result["characters"]
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def _extract_candidates(text: str) -> List[str]:
    """从文本中提取可能的 JSON 数组候选"""
    candidates = []

    # 正则提取最外层 [...]
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        candidates.append(m.group(0))

    # 如果文本本身就是候选且未被正则覆盖
    if text not in candidates:
        candidates.append(text)

    return candidates


def _sanitize_json_string(text: str) -> str:
    """清理 JSON 字符串中的非法控制字符和常见问题

    - 替换未转义的换行符（在字符串值内部）
    - 移除 ASCII 控制字符（保留 \t \n \r）
    - 修复末尾多余逗号（JSON 非法但 Python 合法）
    """
    # 移除除了 \t \n \r 之外的 ASCII 控制字符 (0x00-0x1f)
    sanitized = []
    for ch in text:
        cp = ord(ch)
        if cp < 0x20 and cp not in (0x09, 0x0a, 0x0d):
            # 替换为空格，避免破坏 JSON 结构
            sanitized.append(" ")
        else:
            sanitized.append(ch)

    result = "".join(sanitized)

    # 修复末尾多余逗号：在 ] 或 } 前的逗号
    result = re.sub(r",\s*([}\]])", r"\1", result)

    return result


def _repair_truncated_json(raw_text: str) -> str:
    """尝试修复因 max_tokens 不足而被截断的 JSON 数组

    策略：找到最后一个完整的对象（闭合的 }），截断其后内容，补上 ]
    如果无法找到完整对象，返回原文让后续 fallback 处理。
    """
    # 找到所有 } 的位置（作为对象结束的候选）
    # 从后往前找到最后一个看起来是完整对象结束的 }
    text = raw_text.strip()

    # 去掉末尾明显不完整的片段（如最后一行是半个字符串值）
    # 尝试从最后一个 " 后跟 , 再跟换行和 { 的模式来定位
    # 简单策略：找到最后一个 " 后跟 \n 再跟 ] 或 \n 再跟 } 的位置

    # 如果文本以 ] 结尾，可能已经完整
    if text.endswith("]"):
        return text

    # 策略1：找到最后一个完整的对象（} 后面紧跟 , 或换行）
    # 从后往前扫描，找到最后一个 } 后跟可选空白再跟 , 或直接是数组结束位置
    last_complete = -1
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # 这个 } 闭合了一个顶层对象
                # 检查后面是否只有空白和 , 或直接到数组尾
                after = text[i + 1:i + 50].lstrip()
                if after.startswith(",") or after.startswith("]"):
                    last_complete = i + 1  # 包含 }

    if last_complete > 0:
        repaired = text[:last_complete] + "\n]"
        logger.info(
            "CHARACTER_TRUNCATED_REPAIR: original=%d repaired=%d",
            len(text), len(repaired),
        )
        return repaired

    # 策略2：暴力 — 从最后一个 } 处截断并补 ]
    last_brace = text.rfind("}")
    if last_brace > 0:
        repaired = text[:last_brace + 1] + "\n]"
        logger.info(
            "CHARACTER_TRUNCATED_REPAIR_FALLBACK: original=%d repaired=%d",
            len(text), len(repaired),
        )
        return repaired

    # 无法修复
    return text
