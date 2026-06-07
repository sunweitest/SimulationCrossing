"""上下文压缩模块

当对话轮数超过阈值时，将旧轮压缩为一段故事概要，
通过 DeepSeek API 做摘要，后台执行不阻塞游戏响应。
"""
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
            "请将新内容整合到概要中，形成一段连贯的概要（300-500字）。\n\n"
            f"已有概要：\n{existing_summary}\n\n"
            f"新增剧情：\n{history_text}\n\n"
            "请仅输出更新后的概要文本。"
        )
    else:
        return (
            "你是一个故事摘要助手。请将以下互动历史小说游戏的对话历史"
            "压缩为一段简洁的故事概要（200-400字），保留以下关键信息：\n"
            "- 重要的剧情事件和转折点\n"
            "- 角色做出的关键选择及其后果\n"
            "- 新出现的角色或关系变化\n"
            "- 角色的当前处境和状态\n\n"
            f"对话历史（格式为场景描述与玩家选择交替）：\n\n{history_text}\n\n"
            "请仅输出概要文本。"
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
