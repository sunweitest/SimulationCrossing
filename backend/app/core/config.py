from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "AI Interactive Novel Game"
    VERSION: str = "1.0.0"

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./game.db"

    # JWT配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # DashScope API配置
    DASHSCOPE_API_KEY: str
    SHUIHU_APP_ID: str
    SANGUO_APP_ID: str
    MINGDAI_APP_ID: str
    QINGDAI_APP_ID: str

    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8080"]

    # 次数限制配置
    DAILY_FREE_MESSAGES: int = 26
    DAILY_LOGGED_IN_EXTRA: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
