import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import close_db, init_db
from app.api import auth, game, admin
from app.middleware.rate_limit import RateLimitMiddleware
from contextlib import asynccontextmanager

# 配置业务日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 抑制第三方库的过多日志
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# LLM 相关日志设为 DEBUG，方便排查响应问题
logging.getLogger("llm.deepseek").setLevel(logging.DEBUG)
logging.getLogger("game_service").setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    if settings.AUTO_CREATE_TABLES:
        await init_db()

    # ── 初始化场景图片匹配器 ──
    if settings.DASHSCOPE_API_KEY:
        try:
            from app.services.scene_image_matcher import init_matcher

            project_root = Path(__file__).resolve().parent.parent.parent
            image_dir = project_root / settings.SCENE_IMAGE_DIR
            cache_path = project_root / settings.SCENE_IMAGE_CACHE_PATH

            await init_matcher(
                image_dir=image_dir,
                cache_path=cache_path,
                api_key=settings.DASHSCOPE_API_KEY,
            )
            logger = logging.getLogger("main")
            logger.info("场景图片匹配器初始化完成: %s", image_dir)
        except Exception as e:
            logger = logging.getLogger("main")
            logger.warning("场景图片匹配器初始化失败（非致命）: %s", e)
    else:
        logger = logging.getLogger("main")
        logger.info("DASHSCOPE_API_KEY 未配置，跳过场景图片匹配器")

    yield
    await close_db()


# 创建应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加速率限制中间件
app.add_middleware(RateLimitMiddleware)

# 注册路由
app.include_router(auth.router)
app.include_router(game.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI Interactive Novel Game API",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
