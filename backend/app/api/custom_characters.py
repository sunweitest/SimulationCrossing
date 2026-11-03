"""自定义角色：每个玩家自己的角色，别人看不见，可改可删。"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import CustomCharacter, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/custom-characters", tags=["custom-characters"])


class CustomCharacterIn(BaseModel):
    novel: str
    name: str = Field(min_length=1, max_length=20)
    gender: Optional[str] = None
    age: Optional[int] = None
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


@router.get("", response_model=List[CustomCharacterOut])
async def list_custom_characters(
    novel: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_user(current_user)
    stmt = select(CustomCharacter).where(CustomCharacter.user_id == user.id)
    if novel:
        stmt = stmt.where(CustomCharacter.novel == novel)
    stmt = stmt.order_by(CustomCharacter.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.post("", response_model=CustomCharacterOut, status_code=status.HTTP_201_CREATED)
async def create_custom_character(
    payload: CustomCharacterIn,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_user(current_user)
    row = CustomCharacter(user_id=user.id, **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/{character_id}", response_model=CustomCharacterOut)
async def update_custom_character(
    character_id: int,
    payload: CustomCharacterIn,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
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


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_character(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_user(current_user)
    row = await db.get(CustomCharacter, character_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    await db.delete(row)
    await db.commit()
