import logging
from typing import Optional, Dict, List
from http import HTTPStatus
from dashscope.app import Application
from app.core.config import settings
from app.services.llm.base import LLMProvider

logger = logging.getLogger("llm.dashscope")


class DashScopeProvider(LLMProvider):
    """DashScope (阿里云百炼) LLM 提供者"""

    def __init__(self):
        self._app_ids = {
            "三国演义": settings.SANGUO_APP_ID,
            "水浒传": settings.SHUIHU_APP_ID,
            "明代": settings.MINGDAI_APP_ID,
            "清代": settings.QINGDAI_APP_ID,
            "西游记": settings.XIYOU_APP_ID,
        }

    async def generate(
        self,
        character_info: Dict,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        effective_background = character_info.get('dynamic_background') or character_info.get('background', '无')

        prompt = f"""
        玩家扮演的角色信息如下：
        - 姓名：{character_info['name']}
        - 身份：{character_info['rank']}
        - 背景：{effective_background}
        - 所处世界：{character_info['novel']}
        - 时间节点：{character_info['timeline']}
        玩家做出选择或行动：「{user_input}」
        """.strip()

        novel = character_info['novel']
        app_id = self._app_ids.get(novel)
        if not app_id:
            logger.warning("DASHSCOPE: 未知小说类型 novel=%s", novel)
            return None, session_id

        logger.info("DASHSCOPE: novel=%s character=%s timeline=%s action=%s session=%s",
                     novel, character_info['name'], character_info['timeline'], user_input, session_id)
        logger.debug("DASHSCOPE_PROMPT: %s", prompt)

        full_text = ""
        new_session_id = session_id

        try:
            responses = Application.call(
                api_key=settings.DASHSCOPE_API_KEY,
                app_id=app_id,
                prompt=prompt,
                session_id=session_id,
                stream=True,
                incremental_output=True
            )

            chunk_count = 0
            for response in responses:
                if response.status_code != HTTPStatus.OK:
                    logger.error("DASHSCOPE_ERROR: status=%s message=%s", response.status_code, response.message)
                    return None, session_id

                if response.output.text:
                    full_text += response.output.text
                    chunk_count += 1

                if hasattr(response.output, 'session_id') and response.output.session_id:
                    new_session_id = response.output.session_id

            logger.info("DASHSCOPE_RESPONSE: chunks=%d session=%s chars=%d", chunk_count, new_session_id, len(full_text))
            logger.debug("DASHSCOPE_RAW: %s", full_text)
            return full_text, new_session_id

        except Exception as e:
            logger.exception("DASHSCOPE_EXCEPTION: %s", e)
            return None, session_id
