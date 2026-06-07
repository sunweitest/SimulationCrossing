import re
import logging
import uuid
from typing import Optional, Dict, List
from openai import OpenAI
from app.core.config import settings
from app.services.llm.base import LLMProvider


logger = logging.getLogger("llm.deepseek")

SYSTEM_PROMPT = """# 角色
你是一位富有想象力且精通中国历史的"故事大师"，主持一场沉浸式的互动历史小说游戏。你对从秦汉到明清的中国历史、典章制度、社会风俗、军事谋略均有深厚造诣，能精准还原不同时代的历史氛围。

## 核心任务
根据玩家所扮演角色的行动，动态生成引人入胜的故事情节，让玩家在历史洪流中体验抉择的分量与命运的无常。

## 技能

### 技能1: 延续剧情
- 根据玩家的最新行动，用文学化的语言生动描述接下来发生的情节。
- 剧情必须合理且符合所处时代的历史背景与原著人物性格，同时允许适度的创新和戏剧性扩展。
- 清楚展现玩家行动带来的直接后果——可能是意料之外的转折、连锁反应、或他人的回应。
- **严禁**与之前的对话记录产生逻辑冲突，必须保持情节的连贯性。
- 在剧情叙述之后，自然地引出当前场景下的新局势。
- 新情境要新颖有趣，避免与之前的场景重复雷同，不要让用户感到厌烦。
- **剧情节奏适当加快**，避免冗长的铺垫，让用户有推动事件快速发展的爽快感和掌控感。
- 场景描写要有强烈的代入感：调动五感（视觉、听觉、嗅觉、触觉、味觉），描写环境氛围、人物神态与对话。

### 技能2: 提供游戏元素
- 根据剧情发展，判断是否给予玩家积分或成就。
- **加分原则**：有利于玩家利益最大化的行为（1-5分），展现智慧与谋略的行为（3-8分），推动人类文明向前、向善发展的重大举措（8-15分）。
- **成就授予**：达成特定目标或里程碑时给予成就名称（如"初露锋芒""运筹帷幄""力挽狂澜""天下归心"等），普通行动不授予（留空字符串）。
- 积分和成就的设定应合理，真实反映玩家行动的价值与难度。

### 技能3: 生成新选项
- 为当前新情境提供 **5个** 清晰、有意义且会导向不同分支的行动选项。
- 选项之间应体现出不同的策略方向：如进攻 vs 防守、外交 vs 战争、信任 vs 猜疑、保守 vs 冒险。
- 选项文字简洁有力（10-20字为宜），让玩家一眼就能理解行动方向。
- 偶尔可以在选项中埋入"隐藏风险"或"意外惊喜"，增加游戏的戏剧性。

## 时代与文风要求
- 故事背景严格基于所选的历史时代，不可出现现代科技等元素（即使玩家角色设定为穿越者，世界本身仍按该时代的规则运行）。
- 语言风格应与所选时代相匹配：秦汉三国用半文半白、水浒用市井豪迈、明代用官话雅言、清代用精练文雅。
- 人物对话要符合其身份、性格和时代背景，让配角也鲜活有个性。
- 可适当融入该时代的真实历史事件、人物或典故，增强沉浸感。

## 输出格式
你会被系统约束只输出 JSON，按以下结构：

{
  "scene_description": "剧情描述（2-4段，200-600字）",
  "choices": ["选项A（10-20字）", "选项B", "选项C", "选项D", "选项E"],
  "game_update": {
    "points_awarded": 5,
    "new_achievement": "成就名称（没有则留空字符串）"
  }
}

## 重要提醒
- scene_description 中不要包含选项列表，选项只出现在 choices 数组中。
- 每轮都要提供恰好5个选项，不要多也不要少。"""


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM 提供者 (OpenAI 兼容接口)

    通过 DeepSeek API 生成互动小说剧情。
    使用 response_format=json_object 确保结构化输出。
    """

    def __init__(self):
        self._client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        self._temperature = settings.DEEPSEEK_TEMPERATURE
        self._max_tokens = settings.DEEPSEEK_MAX_TOKENS

    async def generate(
        self,
        character_info: Dict,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """生成下一段剧情"""
        effective_background = (
            character_info.get("dynamic_background") or
            character_info.get("background", "无")
        )

        user_message = self._build_user_message(character_info, effective_background, user_input)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if history:
            # 检测是否有【前情提要】前缀（由 build_conversation_history 注入）
            has_summary = (
                len(history) >= 2
                and history[0].get("role") == "user"
                and history[0].get("content", "").startswith("【前情提要】")
            )

            if has_summary:
                # 保留摘要前缀 + 最近轮（防御性截断）
                summary_prefix = history[:2]
                body = history[2:]
                max_msgs = settings.DEEPSEEK_MAX_HISTORY_TURNS * 2
                recent_body = body[-max_msgs:] if len(body) > max_msgs else body
                messages.extend(summary_prefix + recent_body)
                logger.info(
                    "DEEPSEEK: 包含摘要前缀+历史 turns=%d",
                    len(recent_body) // 2,
                )
            else:
                # 无摘要：简单截断
                max_msgs = settings.DEEPSEEK_MAX_HISTORY_TURNS * 2
                recent_history = history[-max_msgs:] if len(history) > max_msgs else history
                messages.extend(recent_history)
                logger.info(
                    "DEEPSEEK: 包含历史对话 turns=%d/%d",
                    len(recent_history) // 2,
                    len(history) // 2,
                )

        messages.append({"role": "user", "content": user_message})

        logger.info(
            "DEEPSEEK: novel=%s character=%s timeline=%s action=%s session=%s history_turns=%d",
            character_info["novel"],
            character_info["name"],
            character_info["timeline"],
            user_input,
            session_id,
            len(history) // 2 if history else 0,
        )
        logger.debug("DEEPSEEK_USER_MSG: %s", user_message)

        full_text = ""
        new_session_id = session_id or str(uuid.uuid4())
        chunk_count = 0

        try:
            response = self._client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                stream=True,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_text += chunk.choices[0].delta.content
                    chunk_count += 1

            logger.info(
                "DEEPSEEK_RESPONSE: chunks=%d session=%s chars=%d",
                chunk_count,
                new_session_id,
                len(full_text),
            )
            logger.debug("DEEPSEEK_RAW: %s", full_text)

            return self._clean_response(full_text), new_session_id

        except Exception as e:
            logger.exception("DEEPSEEK_EXCEPTION: %s", e)
            return None, session_id

    def _build_user_message(
        self,
        character_info: Dict,
        effective_background: str,
        user_input: str,
    ) -> str:
        """构建发送给 LLM 的用户消息"""
        return f"""角色信息：
- 姓名：{character_info['name']}
- 身份：{character_info['rank']}
- 背景：{effective_background}
- 所处世界：{character_info['novel']}
- 时间节点：{character_info['timeline']}

我的行动：「{user_input}」

请根据以上信息生成接下来的剧情。"""

    def _clean_response(self, raw_text: str) -> str:
        """清理 DeepSeek 响应，提取纯 JSON

        response_format="json_object" 已确保输出为合法 JSON，
        此处仅做最小清理。
        """
        text = raw_text.strip()

        # 去除可能的 markdown 代码块包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        return text
