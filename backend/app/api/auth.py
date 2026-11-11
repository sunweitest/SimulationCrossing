from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging
import re
from typing import Optional
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.models import User
from app.core.timeutil import now_cn
from app.schemas.schemas import UserCreate, UserLogin, Token, UserResponse, NicknameIn
from datetime import timedelta
from app.core.config import settings
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


NICKNAME_MIN, NICKNAME_MAX = 2, 12
_NICKNAME_RESERVED = ("官方", "管理员", "客服", "系统", "gm", "admin", "闯关者", "游客")
_NICKNAME_FORBIDDEN_PAT = re.compile(r"[<>\[\]{}|\\^`]")


def normalize_nickname(raw: Optional[str]) -> Optional[str]:
    """校验并规整昵称。

    - 空 / 全空白 -> None（走「闯关者 + id」兜底，不强制用户起名）
    - 2-12 个字符（中文按 1 个字符算），去掉首尾空白、压缩内部连续空格
    - 拒绝手机号、邮箱、网址：不让用户把联系方式写进公开榜单
    - 拒绝官方/系统类保留词，避免冒充
    """
    if raw is None:
        return None
    name = " ".join(str(raw).split())
    if not name:
        return None
    if not (NICKNAME_MIN <= len(name) <= NICKNAME_MAX):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"昵称需要 {NICKNAME_MIN}-{NICKNAME_MAX} 个字符",
        )
    lowered = name.lower()
    if "@" in name or "http" in lowered or "www." in lowered or re.search(r"\.(com|cn|net|org)\b", lowered):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="昵称不能包含邮箱或网址")
    if re.fullmatch(r"[+\d][\d\s\-()]{5,}", name):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="昵称不能是手机号")
    if any(word in lowered for word in _NICKNAME_RESERVED):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该昵称不可用，请换一个")
    if _NICKNAME_FORBIDDEN_PAT.search(name):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="昵称包含不支持的字符")
    return name


@router.post("/register", response_model=Token, summary="注册账号", responses={400: {"description": "未同意条款 / 缺少邮箱或手机号 / 已被注册"}})
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    创建一个新账号并直接返回令牌。

    - **权限**：公开
    - **请求体**：`email` 或 `phone` 至少填一个；`password` 至少 6 位；`agree_terms` 必须为 `true`
    - **返回**：`access_token` + 用户信息；令牌默认 7 天有效，放在 `Authorization: Bearer <token>`
    - **错误**
      - `400` 未勾选条款 / 未提供邮箱或手机号 / 该邮箱或手机号已被注册（并发重复注册也返回 400）
      - `422` 字段格式不合法（邮箱格式、密码长度等）
    """
    # 必须先同意条款（前端勾选框 + 后端校验，留痕时间用于合规举证）
    if not user_data.agree_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先阅读并同意《服务条款》和《隐私政策》"
        )

    # 验证至少提供了邮箱或手机号
    if not user_data.email and not user_data.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供邮箱或手机号"
        )

    # 检查用户是否已存在
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被注册"
            )

    if user_data.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被注册"
            )

    # 昵称可选；不填就留空，展示时按「闯关者 + id」兜底
    nickname = normalize_nickname(user_data.nickname)

    # 创建用户
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        phone=user_data.phone,
        nickname=nickname,
        hashed_password=hashed_password,
        terms_accepted_at=now_cn()
    )
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        # 并发下两个请求都通过了上面的 select 判重，后到的撞唯一索引：
        # 这里必须兜住，否则用户看到 500。
        await db.rollback()
        logging.getLogger("auth").warning(
            "REGISTER_DUPLICATE: email=%s phone=%s", user_data.email, user_data.phone
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱或手机号已被注册",
        )
    await db.refresh(new_user)

    # 生成令牌
    access_token = create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    user_response = UserResponse.from_orm(new_user)
    return Token(access_token=access_token, user=user_response)


@router.post("/login", response_model=Token, summary="登录", responses={401: {"description": "账号或密码错误"}})
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    用邮箱或手机号 + 密码换取令牌。

    - **权限**：公开
    - **请求体**：`identifier`（邮箱或手机号）、`password`
    - **返回**：`access_token` + 用户信息
    - **错误**：`401` 账号或密码错误；`400` 账号被停用
    """
    # 查找用户（通过邮箱或手机号）
    result = await db.execute(
        select(User).where(
            (User.email == login_data.identifier) | (User.phone == login_data.identifier)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱/手机号或密码错误"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号已被禁用"
        )

    # 生成令牌
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    user_response = UserResponse.from_orm(user)
    return Token(access_token=access_token, user=user_response)


@router.get("/me", response_model=UserResponse, summary="当前用户信息")
async def me(current_user: User = Depends(get_current_active_user)):
    """
    返回当前登录用户的账号信息（含昵称）。

    - **权限**：需要登录
    - **注意**：`email` / `phone` 只返回给用户自己，天梯榜不返回这两项
    """
    return UserResponse.from_orm(current_user)


@router.put(
    "/me/nickname",
    response_model=UserResponse,
    summary="修改昵称",
    responses={422: {"description": "昵称长度/格式不合法，或命中保留词"}},
)
async def update_nickname(
    payload: NicknameIn,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    修改天梯展示昵称，立刻生效。

    - **权限**：需要登录，只能改自己的
    - **规则**：2-12 个字符；不能是手机号、邮箱、网址；不能用「官方」「管理员」「闯关者」等保留词
    - **错误**：`422` 格式不合法
    """
    current_user.nickname = normalize_nickname(payload.nickname)
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.from_orm(current_user)
