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
        """生成剧情文本"""
        ...

    async def generate_choices(
        self,
        scene_description: str,
        character_info: Dict,
    ) -> list[str]:
        """根据场景生成行动选项（可选覆盖，默认返回通用选项）"""
        return ["继续探索", "伺机而动", "随机应变", "与人交谈", "静观其变"]
