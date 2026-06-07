from abc import ABC, abstractmethod
from typing import Optional, Dict, List


class LLMProvider(ABC):
    """LLM 调用抽象基类"""

    @abstractmethod
    async def generate(
        self,
        character_info: Dict,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """生成剧情文本

        Args:
            character_info: 角色信息字典 (name, rank, background, novel, timeline, dynamic_background)
            user_input: 玩家输入的行动
            session_id: 上次对话的 session_id（多轮对话上下文）
            history: 对话历史列表 [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            (response_text, new_session_id)
            response_text: LLM 原始响应文本，传给 parse_llm_response 解析
            new_session_id: 新的 session_id，下次调用传入
        """
        ...
