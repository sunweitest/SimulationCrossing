import re
import ast
import time
import json
import logging
import uuid
from typing import Optional, Dict, List, Callable, Awaitable
from openai import OpenAI
from app.core.config import settings
from app.services.llm.base import LLMProvider

logger = logging.getLogger("llm.deepseek")

# ── Tool 定义（DeepSeek function calling）─────────────────

CHARACTER_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_character",
        "description": (
            "查询故事中已出现过的人物的详细信息，"
            "包括与玩家的关系、好感度（-100到100）、当前状态（存活/死亡/离开）等。"
            "当你需要在剧情中引用或召回某个人物时，"
            "务必先调用此工具查询其最新状态，确保人物行为与关系、好感度一致。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "要查询的人物姓名",
                }
            },
            "required": ["name"],
        },
    },
}

CHARACTER_TOOLS = [CHARACTER_QUERY_TOOL]

# ── System Prompt ─────────────────────────────────────────

SYSTEM_PROMPT = """# 角色
你是一位富有想象力且精通中国历史的"故事大师"，主持一场沉浸式的互动历史小说游戏。你对从秦汉到明清的中国历史、典章制度、社会风俗、军事谋略均有深厚造诣，能精准还原不同时代的历史氛围。

## 核心任务
根据玩家所扮演角色的行动，动态生成引人入胜的故事情节，让玩家在历史洪流中体验抉择的分量与命运的无常。

## 角色关系意识
- 当对话历史中出现【当前人物关系】块时，你必须严格依据其中记录的好感度和关系来塑造人物行为。
- 好感度影响人物对玩家的态度：高好感度（≥50）意味着友善、信任、愿意帮助；低好感度（≤-50）意味着冷漠、猜疑甚至敌对。
- 人物的对话语气、行为选择、是否背叛或帮助玩家，都应与好感度数值一致。
- 随着剧情发展，人物关系会自然变化——如果玩家的行为明确改善了或损害了与某个人物的关系，请根据变化幅度适当调整（后续系统会做结构化更新）。
- 即使对话历史中没有【当前人物关系】块，你也应保持之前出现过的人物行为的一致性——不要遗忘或OOC（角色崩坏）。

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
- 赏罚分明，应给玩家相应的官位提拔、职级提升、财宝等奖励

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
- 语言风格应与所选时代相匹配：秦汉三国用半文半白、水浒用市井豪迈、明代用官话雅言、清代用精练文雅、西游记用神话瑰丽。
- 人物对话要符合其身份、性格和时代背景，让配角也鲜活有个性。
- 可适当融入该时代的真实历史事件、人物或典故，增强沉浸感。

## 输出格式（严格遵守）
你必须**只输出**一个 JSON 对象，不能有任何前缀文字、后缀文字或 markdown 包裹。直接输出：

{
  "scene_description": "剧情描述（200-800字）",
  "choices": ["选项A（10-20字）", "选项B", "选项C", "选项D", "选项E"],
  "game_update": {
    "points_awarded": 5,
    "new_achievement": "成就名称（没有则留空字符串）"
  }
}

## 重要提醒
- 你的回复必须以 `{` 开头，以 `}` 结尾，中间不能有任何非 JSON 内容。
- scene_description 中不要包含选项列表，选项只出现在 choices 数组中。
- scene_description 内的双引号必须转义为 \\\"，换行必须转义为 \\n。
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
            timeout=90.0,  # 单次请求超时 90s
        )
        self._temperature = settings.DEEPSEEK_TEMPERATURE
        self._max_tokens = settings.DEEPSEEK_MAX_TOKENS

    async def generate(
            self,
            character_info: Dict,
            user_input: str,
            session_id: Optional[str] = None,
            history: Optional[List[Dict]] = None,
            tools: Optional[List[Dict]] = None,
            tool_handler: Optional[Callable[[str, str], Awaitable[str]]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """生成下一段剧情

        Args:
            tools: DeepSeek function calling 工具定义列表
            tool_handler: async (name, arguments_json) -> result_str，
                         提供时启用 tool loop，LLM 可主动查询角色信息

        当 tools + tool_handler 同时提供时，自动处理 tool call 循环，
        直到 LLM 返回最终文本或达到最大迭代次数。
        """
        effective_background = (
                character_info.get("dynamic_background") or
                character_info.get("background", "无")
        )

        user_message = self._build_user_message(character_info, effective_background, user_input)

        messages = self._assemble_messages(user_message, history)

        # 估算 token 量（中文约 1.5 字符/token）
        total_chars = sum(len(m["content"]) for m in messages)
        estimated_tokens = total_chars // 1.5

        logger.info(
            "DEEPSEEK_REQ: novel=%s character=%s timeline=%s action=%.40s session=%s "
            "msgs=%d est_tokens=%.0f history_turns=%d tools=%s",
            character_info["novel"],
            character_info["name"],
            character_info["timeline"],
            user_input,
            session_id,
            len(messages),
            estimated_tokens,
            len(history) // 2 if history else 0,
            "on" if tools else "off",
        )
        logger.debug("DEEPSEEK_USER_MSG: %s", user_message)

        new_session_id = session_id or str(uuid.uuid4())
        t_start = time.time()

        # 详细记录发送给 LLM 的消息结构
        logger.debug(
            "DEEPSEEK_MSG_STRUCT: total_msgs=%d sys_chars=%d last_user_chars=%d",
            len(messages),
            len(messages[0]["content"]),
            len(messages[-1]["content"]),
        )
        for i, m in enumerate(messages):
            role = m["role"]
            content_len = len(m["content"])
            preview = m["content"][:80].replace("\n", "\\n")
            logger.debug(
                "DEEPSEEK_MSG[%d]: role=%s len=%d preview=%.80s",
                i, role, content_len, preview,
            )

        # ── Tool call loop ──────────────────────────────
        max_tool_rounds = 3
        use_tools = tools and tool_handler

        try:
            for round_idx in range(max_tool_rounds + 1):
                response = self._client.chat.completions.create(
                    model="deepseek-v4-pro",
                    messages=messages,
                    stream=False,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                    tools=tools if use_tools else None,
                )

                msg = response.choices[0].message

                # 无 tool_calls → 最终响应
                if not msg.tool_calls:
                    full_text = msg.content or ""
                    t_total = time.time() - t_start

                    self._save_raw_log(full_text, new_session_id)

                    head = full_text[:200].replace("\n", "\\n")
                    tail = full_text[-50:].replace("\n", "\\n") if len(full_text) > 200 else ""
                    logger.info(
                        "DEEPSEEK_OK: chars=%d time=%.1fs head=%.200s tail=%.50s",
                        len(full_text), t_total, head, tail,
                    )

                    hex_head = full_text[:80].encode("utf-8", errors="replace").hex(" ")
                    logger.info("DEEPSEEK_HEX(first80): %s", hex_head)

                    visible = full_text.strip()
                    if not visible:
                        logger.warning(
                            "DEEPSEEK_EMPTY: 响应全为空白字符 raw_len=%d time=%.1fs",
                            len(full_text), t_total,
                        )
                        return None, session_id

                    cleaned = self._clean_response(full_text)
                    if not cleaned:
                        logger.warning(
                            "DEEPSEEK_CLEAN_EMPTY: 清理后为空 raw_len=%d cleaned_len=%d",
                            len(full_text), len(cleaned),
                        )
                        return None, session_id

                    return cleaned, new_session_id

                # 有 tool_calls → 执行工具，结果喂回 LLM
                logger.info(
                    "DEEPSEEK_TOOL_CALLS: round=%d calls=%d",
                    round_idx, len(msg.tool_calls),
                )

                # 将 assistant 消息（含 tool_calls）加入历史
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # 执行每个 tool call
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = tc.function.arguments
                    try:
                        result = await tool_handler(tool_name, tool_args)
                    except Exception as e:
                        logger.exception(
                            "TOOL_HANDLER_ERROR: tool=%s args=%s err=%s",
                            tool_name, tool_args, e,
                        )
                        result = json.dumps({"error": str(e)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                    logger.info(
                        "TOOL_RESULT: tool=%s args=%s result_len=%d",
                        tool_name, tool_args, len(result),
                    )

            # 超过最大轮次仍未得到最终响应
            logger.warning(
                "DEEPSEEK_TOOL_LOOP_EXHAUSTED: max_rounds=%d",
                max_tool_rounds,
            )
            return None, session_id

        except Exception as e:
            t_elapsed = time.time() - t_start
            logger.exception(
                "DEEPSEEK_ERR: time=%.1fs error=%s",
                t_elapsed, e,
            )
            return None, session_id

    def _assemble_messages(
        self,
        user_message: str,
        history: Optional[List[Dict]],
    ) -> List[Dict]:
        """组装发送给 LLM 的完整消息列表

        提取自 generate() 的消息构建逻辑，方便复用。
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if history:
            has_summary = (
                len(history) >= 2
                and history[0].get("role") == "user"
                and history[0].get("content", "").startswith("【前情提要】")
            )

            if has_summary:
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
                max_msgs = settings.DEEPSEEK_MAX_HISTORY_TURNS * 2
                recent_history = history[-max_msgs:] if len(history) > max_msgs else history
                messages.extend(recent_history)
                logger.info(
                    "DEEPSEEK: 包含历史对话 turns=%d/%d",
                    len(recent_history) // 2,
                    len(history) // 2,
                )

        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _save_raw_log(raw_text: str, session_id: str) -> None:
        """将 DeepSeek 原始响应写入日志文件"""
        try:
            from pathlib import Path
            from datetime import datetime
            log_dir = Path(__file__).resolve().parent.parent.parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            fname = log_dir / f"deepseek_raw_{ts}_session_{session_id[:8]}.txt"
            fname.write_text(raw_text, encoding="utf-8")
            logger.info("DEEPSEEK_LOG_FILE: %s", fname.name)
        except Exception as e:
            logger.warning("DEEPSEEK_LOG_FILE_ERR: %s", e)

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
        """清理 DeepSeek 响应，提取纯 JSON"""
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text

    @staticmethod
    def _parse_choices(text: str) -> Optional[list]:
        """多级 fallback 解析 LLM 返回的选项数组。

        LLM 返回格式不稳定，可能包含：
        - 纯 JSON 数组：["选项A", "选项B", "选项C"]
        - markdown 围栏包裹（已在调用方处理）
        - 数组外有多余文字：以下是选项：["A","B"] 请选择
        - 单引号 Python 列表：['选项A', '选项B', '选项C']
        - 末尾多余逗号：["A", "B",]（JSON 非法，但 Python 合法）

        解析策略（按优先级逐级降级）：
        ① 正则提取最外层的 [...]，去掉 LLM 可能在数组外追加的废话
        ② json.loads —— 覆盖绝大多数标准 JSON 返回
        ③ ast.literal_eval —— 覆盖单引号、末尾逗号等 Python 字面量写法
        ④ json.loads(原文) —— 兜底：原文就是一个干净数组但含嵌套结构时
        全部失败 → 返回 None，由调用方使用默认选项
        """
        # ① 正则提取 [...]，滤掉 LLM 可能在数组前后追加的解释文字
        m = re.search(r"\[.*\]", text, re.DOTALL)
        bracketed = m.group(0) if m else text

        # ② json.loads：处理标准双引号 JSON 数组
        try:
            result = json.loads(bracketed)
            if isinstance(result, list):
                return [str(item) for item in result]
        except (json.JSONDecodeError, ValueError):
            pass

        # ③ ast.literal_eval：处理单引号 Python 列表、混合引号、末尾逗号等 JSON 非法但 Python 合法的写法
        try:
            result = ast.literal_eval(bracketed)
            if isinstance(result, list):
                return [str(item) for item in result]
        except (ValueError, SyntaxError):
            pass

        # ④ 兜底：对整个原文做 json.loads（原文本身就是干净数组时）
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [str(item) for item in result]
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    async def generate_choices(
            self,
            scene_description: str,
            character_info: Dict,
    ) -> list[str]:
        """根据场景描述，轻量调用 LLM 生成 5 个行动选项。

        这是一个简短的独立调用，不需要历史上下文。
        """
        prompt = f"""角色：{character_info['name']}（{character_info['rank']}），所处世界：{character_info['novel']}，时间节点：{character_info['timeline']}。

当前场景：
{scene_description[:600]}

请根据以上场景，为玩家生成5个有意义且导向不同分支的行动选项。
要求：每个选项10-20字，简洁有力。只输出一个数组，用于python解析成列表。如: ["选项A", "选项B", "选项C", "选项D", "选项E"]，不要其他额外内容。"""

        try:
            response = self._client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.7,
                max_tokens=256,
            )
            text = (response.choices[0].message.content or "").strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

            choices = self._parse_choices(text)
            if isinstance(choices, list) and len(choices) >= 1:
                # 补齐到 5 个
                defaults = ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]
                while len(choices) < 5:
                    for d in defaults:
                        if d not in choices:
                            choices.append(d)
                            break
                logger.info("CHOICES_GEN_OK: count=%d", len(choices))
                return choices[:5]
            else:
                raise ValueError("Not a valid choices array")
        except Exception as e:
            logger.warning("CHOICES_GEN_FAIL: %s", e)
            return ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]
