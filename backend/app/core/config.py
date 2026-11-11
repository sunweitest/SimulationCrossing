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
    # 接口地址与模型名都可通过 .env 覆盖，换网关/换模型不用改代码
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"      # 主模型：剧情生成、流式输出、工具循环、行动选项
    DEEPSEEK_PRO_MODEL: str = "deepseek-v4-flash"  # 上下文压缩等任务，默认与主模型一致

    # DeepSeek 模型参数
    DEEPSEEK_TEMPERATURE: float = 0.8        # 创造性（0-2），越高越有创意
    DEEPSEEK_MAX_TOKENS: int = 2096          # 最大输出 token 数
    DEEPSEEK_MAX_HISTORY_TURNS: int = 5      # 保留的最近对话轮数（减少上下文减少出错）
    # 关闭推理模型的思考：reasoning 计入 max_tokens，偶发把预算吃光导致 content 为空；
    # 关掉后延迟明显下降、输出更稳定，代价是复杂剧情的推理略弱
    DEEPSEEK_DISABLE_THINKING: bool = True

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
    # 行动选项/积分/成就 是否优先用 Qwen 生成；false（默认）= 统一走 DeepSeek
    # ── LLM 故障转移 ─────────────────────────────────────
    # 主链路 DeepSeek 直连超时/503/限流时，自动切到阿里云百炼的同名模型，
    # 用户无感知；两条都失败才走兜底文案。
    LLM_FAILOVER_ENABLED: bool = True
    LLM_FALLBACK_BASE_URL: str = "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    LLM_FALLBACK_MODEL: str = "deepseek-v4.1-flash"
    LLM_FALLBACK_METADATA_MODEL: str = "qwen-plus"
    LLM_PRIMARY_TIMEOUT: float = 45.0
    LLM_METADATA_TIMEOUT: float = 25.0
    LLM_PRIMARY_MAX_RETRIES: int = 1
    LLM_FIRST_TOKEN_TIMEOUT: float = 8.0   # 首字迟迟不来就换链路，别让用户对着光标等

    USE_QWEN_METADATA: bool = False

    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8080"]

    # 每回合生成的行动选项数量（越多选项越长，移动端越挤）
    CHOICE_COUNT: int = 3

    # 次数限制配置
    DAILY_FREE_MESSAGES: int = 5
    DAILY_LOGGED_IN_EXTRA: int = 3
    DAILY_UNLIMITED_CAP: int = 50  # 不限次卡的单日硬上限（防脚本）

    # 场景图片匹配
    SCENE_IMAGE_DIR: str = "frontend/public/images/scene"  # 图片目录，相对项目根目录
    SCENE_IMAGE_CACHE_PATH: str = "backend/cache/scene_embeddings.json"  # 向量缓存文件
    SFX_DIR: str = "frontend/public/audio/sfx"  # 音效公共库
    SFX_MANIFEST: str = "content/sfx.json"  # 音效描述与标签
    SFX_CACHE_PATH: str = "backend/cache/sfx_embeddings.json"  # 音效向量缓存

    # 管理后台
    ADMIN_KEY: str = "admin-secret-change-me"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
