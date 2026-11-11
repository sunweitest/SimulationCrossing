import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import close_db, init_db
from app.api import auth, game, admin, community, custom_characters
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

            from app.services.sfx_matcher import init_sfx_matcher

            await init_sfx_matcher(
                audio_dir=project_root / settings.SFX_DIR,
                cache_path=project_root / settings.SFX_CACHE_PATH,
                manifest_path=project_root / settings.SFX_MANIFEST,
                api_key=settings.DASHSCOPE_API_KEY,
            )
            logger.info("音效匹配器初始化完成: %s", settings.SFX_DIR)
        except Exception as e:
            logger = logging.getLogger("main")
            logger.warning("场景图片匹配器初始化失败（非致命）: %s", e)
    else:
        logger = logging.getLogger("main")
        logger.info("DASHSCOPE_API_KEY 未配置，跳过场景图片匹配器")

    yield
    await close_db()


# 创建应用实例
API_DESCRIPTION = """
互动小说游戏后端。玩家选择一个世界（三国、红楼、废土……）与一个时间节点，
以某个角色（预设或自定义）穿越进去，每一回合提交一个行动，模型生成剧情、选项与判定。

## 认证

- 大部分游戏接口对游客开放，登录后存档会绑定到账号。
- 需要登录的接口在本文档中用锁标记；请求头：`Authorization: Bearer <access_token>`，
  令牌由 `/api/auth/register` 或 `/api/auth/login` 返回。
- 管理后台接口需要 `X-Admin-Key` 请求头。

## 时间与时区

所有业务时间按 **Asia/Shanghai (UTC+8)** 计算，每日配额在北京时间 0 点重置。

## 配额

| 身份 | 每日次数 | 说明 |
| --- | --- | --- |
| 游客 | 5 次/天 | 按客户端 IP 计 |
| 登录用户 | 8 次/天 | 按账号计 |

调用 `/api/game/quota` 查询剩余次数；只有成功产生剧情（响应码 < 400）才计一次。
额外次数与包月不限次优先于每日额度消耗。

## 流式接口

`POST /api/game/action/stream` 返回 `text/event-stream`，事件依次为
`status` → `story_chunk`(多次) → `status` → `scene` → `done`，出错时可能提前出现 `error`。
前端应以 `scene` 事件为准，不要用拼接的增量文本覆盖完整场景。

## 通用错误码

| 状态码 | 含义 |
| --- | --- |
| 400 | 参数语义错误（如注册未同意条款、重复邮箱） |
| 401 | 未登录或令牌失效 |
| 403 | 无权访问该存档（归属校验） |
| 404 | 资源不存在 |
| 409 | 对局已结束（主角死亡） |
| 422 | 请求体校验失败（字段缺失、超长、类型错误） |
| 429 | 今日次数用尽或触发限流 |
| 500 | 服务端异常（LLM 不可用时已配置自动切换） |

## 内容来源

世界、角色、时间节点、使命的**唯一来源**是仓库中的 `content/worlds/*.json`，
通过 `scripts/import_content.py` 导入数据库。管理后台的增删改会被下次导入覆盖，
线上内容请改 JSON。
"""

OPENAPI_TAGS = [
    {"name": "认证", "description": "注册、登录、发放令牌。"},
    {"name": "游戏", "description": "开局、行动、存档读取、回溯。核心玩法接口。"},
    {"name": "社区", "description": "世界点击、投票、天梯榜。均为公开接口。"},
    {"name": "自定义角色", "description": "玩家私有的自定义角色，仅创建者本人可见。"},
    {"name": "管理后台", "description": "内容与用户管理，需要 `X-Admin-Key` 请求头。"},
    {"name": "系统", "description": "健康检查与元信息。"},
]

app = FastAPI(
    title="穿越模拟 · 互动小说 API",
    description=API_DESCRIPTION,
    version=settings.VERSION,
    contact={"name": "SimulationCrossing", "url": "https://wanchuanyue.com"},
    license_info={"name": "AGPL-3.0", "url": "https://www.gnu.org/licenses/agpl-3.0.html"},
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
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
app.include_router(community.router)
app.include_router(custom_characters.router)


@app.get("/", tags=["系统"], summary="服务元信息")
async def root():
    """返回服务名、版本与文档地址，可用于探活。

    根路径不触达数据库，只做常量返回。
    """
    return {
        "message": "AI Interactive Novel Game API",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check():
    """健康检查，供负载均衡 / 监控探活。

- **返回**：`{"status": "ok"}`
- **说明**：只表示进程可响应，不校验数据库与 Redis；需要深度检查请结合业务接口。
"""
    return {"status": "ok"}
