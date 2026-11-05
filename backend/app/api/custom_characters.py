"""自定义角色：每个玩家自己的角色，别人看不见，可改可删。"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import CustomCharacter, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/custom-characters", tags=["自定义角色"])


class CustomCharacterIn(BaseModel):
    novel: str
    name: str = Field(min_length=1, max_length=20)
    gender: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=1, le=120)
    rank: Optional[str] = None
    background: Optional[str] = None


class CustomCharacterOut(BaseModel):
    id: int
    novel: str
    name: str
    gender: Optional[str]
    age: Optional[int]
    rank: Optional[str]
    background: Optional[str]

    class Config:
        from_attributes = True


def _require_user(current_user: Optional[User]) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录后才能保存自定义角色",
        )
    return current_user


@router.get("", response_model=List[CustomCharacterOut], summary="我的自定义角色")
async def list_custom_characters(
    novel: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    列出当前登录用户在某世界创建的角色（别人不可见）。

    - **权限**：登录用户
    - **参数**：`novel` 可选，缺省返回全部世界
    - **错误**：`401` 未登录
    """
    user = _require_user(current_user)
    stmt = select(CustomCharacter).where(CustomCharacter.user_id == user.id)
    if novel:
        stmt = stmt.where(CustomCharacter.novel == novel)
    stmt = stmt.order_by(CustomCharacter.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.post("", response_model=CustomCharacterOut, status_code=status.HTTP_201_CREATED, summary="创建自定义角色", responses={401: {"description": "未登录"}})
async def create_custom_character(
    payload: CustomCharacterIn,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    保存一个自定义角色到「我的角色」。

    - **权限**：登录用户
    - **请求体**：`novel`、`name`（1–20 字）、`gender`、`age`（1–120）、`rank`、`background`
    - **返回**：`201` + 角色
    - **错误**：`401` 未登录；`422` 字段不合法
    """
    user = _require_user(current_user)
    row = CustomCharacter(user_id=user.id, **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/{character_id}", response_model=CustomCharacterOut, summary="修改自定义角色", responses={401: {"description": "未登录"}, 404: {"description": "不存在或不是你的角色"}})
async def update_custom_character(
    character_id: int,
    payload: CustomCharacterIn,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    整体更新一个自定义角色。

    - **权限**：仅创建者本人（别人的角色一律 `404`，不暴露是否存在）
    - **返回**：更新后的角色
    - **错误**：`401` 未登录；`404` 不存在或不是你的；`422` 字段不合法
    """
    user = _require_user(current_user)
    row = await db.get(CustomCharacter, character_id)
    # 不属于自己的一律当作不存在，避免探测别人有哪些角色
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除自定义角色", responses={401: {"description": "未登录"}, 404: {"description": "不存在或不是你的角色"}})
async def delete_custom_character(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    删除一个自定义角色（不影响已开始的存档）。

    - **权限**：仅创建者本人
    - **返回**：`204`
    - **错误**：`401` 未登录；`404` 不存在或不是你的
    """
    user = _require_user(current_user)
    row = await db.get(CustomCharacter, character_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    await db.delete(row)
    await db.commit()
