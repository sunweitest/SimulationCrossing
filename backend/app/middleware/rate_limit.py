from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import date
from typing import Optional
import redis.asyncio as redis
from redis.exceptions import RedisError
from app.core.config import settings
from app.core.security import verify_token
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

        is_action = request.url.path == "/api/game/action"
        limit_key = None
        use_daily_count = True
        is_unlimited = False

        if is_action:
            # 获取用户标识
            user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
            if not user_id:
                auth_header = request.headers.get("authorization", "")
                scheme, _, token = auth_header.partition(" ")
                if scheme.lower() == "bearer" and token:
                    payload = verify_token(token)
                    user_id = payload.get("sub") if payload else None

            if user_id:
                limit_key = f"rate_limit:user:{user_id}:{date.today()}"
                daily_limit = settings.DAILY_FREE_MESSAGES + settings.DAILY_LOGGED_IN_EXTRA

                try:
                    # 1. 检查包月不限次数（30 天）
                    unlimited_key = f"rate_limit:user:{user_id}:unlimited"
                    if await self.redis_client.exists(unlimited_key):
                        is_unlimited = True
                        use_daily_count = False

                    # 2. 检查额外配额
                    if not is_unlimited:
                        extra_key = f"rate_limit:user:{user_id}:extra"
                        extra = await self.redis_client.get(extra_key)
                        if extra and int(extra) > 0:
                            # 有额外配额，消耗额外配额，不计入每日次数
                            use_daily_count = False

                    # 3. 正常每日限制检查
                    if use_daily_count:
                        current_count = await self.redis_client.get(limit_key)
                        if current_count and int(current_count) >= daily_limit:
                            return JSONResponse(
                                status_code=429,
                                content={
                                    "detail": {
                                        "message": "今日消息次数已用完",
                                        "needs_login": False,
                                        "daily_limit": daily_limit,
                                        "remaining": 0,
                                    }
                                }
                            )
                except RedisError as exc:
                    print(f"Redis限流不可用，已放行本次请求: {exc}")
            else:
                # 未登录用户
                client_ip = request.client.host
                user_agent = request.headers.get("user-agent", "")
                fingerprint = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
                limit_key = f"rate_limit:guest:{fingerprint}:{date.today()}"
                daily_limit = settings.DAILY_FREE_MESSAGES

                try:
                    current_count = await self.redis_client.get(limit_key)
                    if current_count and int(current_count) >= daily_limit:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "detail": {
                                    "message": "今日免费次数已用完，请登录继续",
                                    "needs_login": True,
                                    "daily_limit": daily_limit,
                                    "remaining": 0,
                                }
                            }
                        )
                except RedisError as exc:
                    print(f"Redis限流不可用，已放行本次请求: {exc}")

        response = await call_next(request)

        # 请求成功后扣减次数
        if is_action and response.status_code < 400 and limit_key:
            try:
                if is_unlimited:
                    pass  # 包月用户不扣次数
                elif not use_daily_count:
                    # 使用额外配额的用户：扣减额外配额
                    extra_key = f"rate_limit:user:{user_id}:extra"
                    await self.redis_client.decr(extra_key)
                else:
                    # 正常每日计数
                    await self.redis_client.incr(limit_key)
                    await self.redis_client.expire(limit_key, 86400)
            except RedisError:
                pass

        return response
