"""管理后台 API

提供用户查询、追加次数、包月不限次数等功能。
使用 Redis 存储额外配额和包月标记。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import settings
from app.models.models import User
from datetime import date
import redis.asyncio as redis

logger = logging.getLogger("admin_api")

router = APIRouter(prefix="/api/admin", tags=["管理后台"])

_redis: redis.Redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
    return _redis


async def _verify_admin(x_admin_key: str = Header(...)):
    """验证管理后台密钥"""
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="无效的管理密钥")
    return True


def _extra_quota_key(user_id: int) -> str:
    return f"rate_limit:user:{user_id}:extra"


def _unlimited_key(user_id: int) -> str:
    """包月不限次数标记，30 天过期"""
    return f"rate_limit:user:{user_id}:unlimited"


# ── 用户查询 ──────────────────────────────────────────────

@router.get("/lookup")
async def lookup_user(
    q: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(_verify_admin),
):
    """根据邮箱或手机号查找用户"""
    result = await db.execute(
        select(User).where((User.email == q) | (User.phone == q))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="未找到该用户")

    r = _get_redis()

    # 查询当前额外配额和包月状态
    extra = await r.get(_extra_quota_key(user.id)) or "0"
    unlimited_key = _unlimited_key(user.id)
    unlimited_ttl = await r.ttl(unlimited_key)

    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "extra_quota": int(extra),
        "is_unlimited": unlimited_ttl > 0,
        "unlimited_days_left": max(0, unlimited_ttl // 86400) if unlimited_ttl > 0 else 0,
    }


# ── 追加次数 ──────────────────────────────────────────────

@router.post("/add-quota")
async def add_quota(
    user_id: int,
    amount: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(_verify_admin),
):
    """给指定用户追加额外次数"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="次数必须大于0")

    # 确认用户存在
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    r = _get_redis()
    key = _extra_quota_key(user_id)
    new_total = await r.incrby(key, amount)
    # 额外配额 30 天过期
    await r.expire(key, 86400 * 30)
    # 清除当天的计数缓存，让用户立即生效
    today_key = f"rate_limit:user:{user_id}:{date.today()}"
    await r.delete(today_key)

    logger.info("ADMIN: add_quota user=%s amount=%d total_extra=%d", user_id, amount, new_total)

    return {
        "message": f"已为用户 {user.email or user.phone} 追加 {amount} 次",
        "extra_quota": new_total,
    }


# ── 包月不限次数 ──────────────────────────────────────────

@router.post("/monthly-unlimited")
async def set_monthly_unlimited(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(_verify_admin),
):
    """给指定用户开通本月不限次数"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    r = _get_redis()
    key = _unlimited_key(user_id)

    # 30 天包月
    ttl = 30 * 86400

    await r.set(key, "1", ex=ttl)
    # 清除当天的计数缓存
    today_key = f"rate_limit:user:{user_id}:{date.today()}"
    await r.delete(today_key)

    logger.info("ADMIN: monthly_unlimited user=%s days=30", user_id)

    return {
        "message": f"已为用户 {user.email or user.phone} 开通30天不限次数",
        "days_left": 30,
    }


@router.delete("/monthly-unlimited")
async def cancel_monthly_unlimited(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(_verify_admin),
):
    """取消用户的本月不限次数"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    r = _get_redis()
    key = _unlimited_key(user_id)
    await r.delete(key)

    logger.info("ADMIN: cancel_unlimited user=%s", user_id)

    return {"message": f"已取消用户 {user.email or user.phone} 的本月不限次数"}
