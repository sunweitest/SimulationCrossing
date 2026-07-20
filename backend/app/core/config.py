from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "AI Interactive Novel Game"
    VERSION: str = "1.0.0"

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/simulation_crossing"
    AUTO_CREATE_TABLES: bool = False

    # JWT配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # LLM 配置
    LLM_PROVIDER: str = "dashscope"  # "dashscope" 或 "deepseek"

    # DashScope API配置（仅 LLM_PROVIDER=dashscope 时需要）
    DASHSCOPE_API_KEY: str = ""
    SHUIHU_APP_ID: str = ""
    SANGUO_APP_ID: str = ""
    MINGDAI_APP_ID: str = ""
    QINGDAI_APP_ID: str = ""
    XIYOU_APP_ID: str = ""

    # DeepSeek API配置（仅 LLM_PROVIDER=deepseek 时需要）
    DEEPSEEK_API_KEY: str = ""

    # DeepSeek 模型参数
    DEEPSEEK_TEMPERATURE: float = 0.8        # 创造性（0-2），越高越有创意
    DEEPSEEK_MAX_TOKENS: int = 2096          # 最大输出 token 数
    DEEPSEEK_MAX_HISTORY_TURNS: int = 5      # 保留的最近对话轮数（减少上下文减少出错）

    # 上下文压缩配置
    CONTEXT_COMPRESSION_THRESHOLD: int = 1   # 触发压缩的对话轮数阈值（超过此值开始压缩旧轮，设1=第2轮起压缩）
    CONTEXT_RECENT_TURNS: int = 1            # 压缩后保留的最近完整轮数

    # 角色追踪配置
    CHARACTER_EXTRACTION_MODEL: str = "deepseek-v4-flash"  # 角色提取使用的模型
    CHARACTER_EXTRACTION_TEMPERATURE: float = 0.2          # 低温度确保结构化输出

    # Qwen OpenAI兼容接口，用于流式剧情和结构化游戏元素生成
    QWEN_BASE_URL: str = "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    QWEN_METADATA_MODEL: str = "qwen-plus"

    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8080"]

    # 次数限制配置
    DAILY_FREE_MESSAGES: int = 6
    DAILY_LOGGED_IN_EXTRA: int = 2

    # 场景图片匹配
    SCENE_IMAGE_DIR: str = "frontend/public/images/scene"  # 图片目录，相对项目根目录
    SCENE_IMAGE_CACHE_PATH: str = "backend/cache/scene_embeddings.json"  # 向量缓存文件

    # 管理后台
    ADMIN_KEY: str = "admin-secret-change-me"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
