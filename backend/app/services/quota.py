"""次数限制：key 规则与状态计算

限流中间件（app/middleware/rate_limit.py）和「查询剩余次数」接口共用这里的规则，
避免两边 key 格式各写一套导致对不上。
"""
from datetime import date
import hashlib
from typing import Optional

from app.core.config import settings


# ── Redis key ─────────────────────────────────────────────

def user_daily_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:{date.today()}"


def user_extra_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:extra"


def user_unlimited_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:unlimited"


def guest_daily_key(request) -> str:
    """未登录用户按 IP + UA 指纹计数"""
    host = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    fingerprint = hashlib.md5(f"{host}:{ua}".encode()).hexdigest()
    return f"rate_limit:guest:{fingerprint}:{date.today()}"


# ── 状态查询 ──────────────────────────────────────────────

async def get_quota_status(redis_client, request, user=None) -> dict:
    """返回当前身份的次数状态。

    已登录：每日 6+2 次，另有额外配额与包月不限次数
    未登录：每日 6 次，用完需要登录
    """
    if user is not None:
        daily_limit = settings.DAILY_FREE_MESSAGES + settings.DAILY_LOGGED_IN_EXTRA
        used = int(await redis_client.get(user_daily_key(user.id)) or 0)
        extra = int(await redis_client.get(user_extra_key(user.id)) or 0)
        unlimited = bool(await redis_client.exists(user_unlimited_key(user.id)))
        is_guest = False
    else:
        daily_limit = settings.DAILY_FREE_MESSAGES
        used = int(await redis_client.get(guest_daily_key(request)) or 0)
        extra = 0
        unlimited = False
        is_guest = True

    daily_remaining = max(0, daily_limit - used)

    return {
        "is_guest": is_guest,
        "daily_limit": daily_limit,
        "used_today": used,
        "daily_remaining": daily_remaining,
        "extra_quota": max(0, extra),
        "is_unlimited": unlimited,
        # 还能用几次：不限次数为 None；否则每日剩余 + 额外配额
        "remaining": None if unlimited else daily_remaining + max(0, extra),
    }
