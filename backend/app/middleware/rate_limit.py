from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import date
from typing import Optional
import redis.asyncio as redis
from app.core.config import settings
import hashlib


class RateLimitMiddleware(BaseHTTPMiddleware):
    """消息次数限制中间件"""

    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None

    async def dispatch(self, request: Request, call_next):
        # 初始化Redis连接
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )

        # 只对游戏行动API进行限制
        if request.url.path == "/api/game/action":
            # 获取用户标识
            user_id = request.state.user_id if hasattr(request.state, 'user_id') else None

            if user_id:
                # 已登录用户
                key = f"rate_limit:user:{user_id}:{date.today()}"
                daily_limit = settings.DAILY_FREE_MESSAGES + settings.DAILY_LOGGED_IN_EXTRA
            else:
                # 未登录用户，使用IP和User-Agent生成指纹
                client_ip = request.client.host
                user_agent = request.headers.get("user-agent", "")
                fingerprint = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
                key = f"rate_limit:guest:{fingerprint}:{date.today()}"
                daily_limit = settings.DAILY_FREE_MESSAGES

            # 检查次数
            current_count = await self.redis_client.get(key)
            if current_count and int(current_count) >= daily_limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "今日消息次数已用完" if user_id else "今日免费次数已用完，请登录继续",
                        "needs_login": not user_id,
                        "daily_limit": daily_limit,
                        "remaining": 0
                    }
                )

            # 增加计数
            await self.redis_client.incr(key)
            await self.redis_client.expire(key, 86400)  # 24小时过期

        response = await call_next(request)
        return response
