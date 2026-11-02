"""次数限制：key 规则与状态计算

限流中间件（app/middleware/rate_limit.py）和「查询剩余次数」接口共用这里的规则，
避免两边 key 格式各写一套导致对不上。
"""
from datetime import date
from typing import Optional

from app.core.config import settings


# ── Redis key ─────────────────────────────────────────────

def user_daily_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:{date.today()}"


def user_extra_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:extra"


def user_unlimited_key(user_id) -> str:
    return f"rate_limit:user:{user_id}:unlimited"


def client_ip(request) -> str:
    """取真实客户端 IP。

    nginx 在反代时设置了 X-Real-IP / X-Forwarded-For，直连时才有 request.client。
    只按 IP 计数是刻意的：一旦把 User-Agent 混进指纹，换浏览器、隐身窗口、
    甚至 UA 版本变化都会生成新 key，额度就白给了。
    """
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def guest_daily_key(request) -> str:
    """未登录用户：按真实 IP 每天一个额度，与设备/浏览器/新开的游戏都无关"""
    return f"rate_limit:guest:ip:{client_ip(request)}:{date.today()}"


# ── 状态查询 ──────────────────────────────────────────────

async def get_quota_status(redis_client, request, user=None) -> dict:
    """返回当前身份的次数状态。

    未登录：按 IP 每天 DAILY_FREE_MESSAGES 次（跨会话累计，换浏览器不重置）
    已登录：DAILY_FREE_MESSAGES + DAILY_LOGGED_IN_EXTRA，另有额外配额与包月不限次数
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
        # 登录后的每日额度，前端提示文案用，避免在页面里写死数字
        "login_limit": settings.DAILY_FREE_MESSAGES + settings.DAILY_LOGGED_IN_EXTRA,
        "used_today": used,
        "daily_remaining": daily_remaining,
        "extra_quota": max(0, extra),
        "is_unlimited": unlimited,
        # 还能用几次：不限次数为 None；否则每日剩余 + 额外配额
        "remaining": None if unlimited else daily_remaining + max(0, extra),
    }
