"""社区功能：世界卡点击埋点、想看世界的投票、天梯排行榜"""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import (
    CharacterTimeline,
    User,
    GameSession,
    NovelConfig,
    PresetCharacter,
    TimelineConfig,
    WorldClickEvent,
    WorldVote,
)
from app.core.timeutil import now_cn
from datetime import timedelta
from app.services.quota import client_ip

router = APIRouter(prefix="/api/community", tags=["社区"])

# 候选题材：还没有做、但用户可能想要的
VOTE_CANDIDATES = [
    {"name": "聊斋志异", "hint": "志怪短篇，一局一个故事"},
    {"name": "隋唐演义", "hint": "瓦岗英雄、隋末群雄"},
    {"name": "镜花缘", "hint": "海外奇国，荒诞风物"},
    {"name": "楚汉争霸", "hint": "项羽刘邦，四年定天下"},
    {"name": "南宋抗金", "hint": "岳家军与十二道金牌"},
    {"name": "丧尸末日", "hint": "城市群感染，生存与人性"},
    {"name": "蒸汽朋克上海滩", "hint": "1930 年代 + 机械改造"},
    {"name": "克苏鲁·民国诡事", "hint": "旧上海 + 不可名状"},
]


def _voter_key(request: Request, user: Optional[object]) -> str:
    if user is not None:
        return f"u:{getattr(user, 'id', 0)}"
    ip = client_ip(request) or "unknown"
    return "ip:" + hashlib.sha256(ip.encode()).hexdigest()[:24]


# --------------------------------------------------------------- 世界角色
@router.get("/world/{novel}/characters", summary="世界的全部角色")
async def list_world_characters(novel: str, db: AsyncSession = Depends(get_db)):
    """
    角色选择页数据：预设角色 + 小人物 + 头像 + 可玩节点。

    - **权限**：公开
    - **返回**：`{"novel": ..., "characters": [{name, rank, age, gender, is_minor, image, timelines[]}]}`
    """
    chars = (
        await db.execute(
            select(PresetCharacter)
            .where(PresetCharacter.novel == novel)
            .order_by(PresetCharacter.is_minor, PresetCharacter.id)
        )
    ).scalars().all()
    if not chars:
        raise HTTPException(status_code=404, detail="该世界暂无角色")

    tl_order = dict(
        (
            await db.execute(
                select(TimelineConfig.name, TimelineConfig.sort_order)
                .join(NovelConfig, NovelConfig.id == TimelineConfig.novel_id)
                .where(NovelConfig.name == novel)
            )
        ).all()
    )

    ids = [c.id for c in chars]
    links = (
        await db.execute(
            select(CharacterTimeline).where(CharacterTimeline.character_id.in_(ids))
        )
    ).scalars().all()
    by_char: dict[int, list[CharacterTimeline]] = {}
    for l in links:
        by_char.setdefault(l.character_id, []).append(l)

    out = []
    for c in chars:
        tls = sorted(by_char.get(c.id, []), key=lambda x: tl_order.get(x.timeline, 99))
        out.append(
            {
                "name": c.name,
                "gender": c.gender or "",
                "age": c.age or 0,
                "rank": c.rank or "",
                "background": c.background or "",
                "starting_points": c.starting_points or 0,
                "is_minor": bool(c.is_minor),
                "image": c.image or "",
                "timelines": [
                    {"name": t.timeline, "background": t.background or ""} for t in tls
                ],
            }
        )
    return {"novel": novel, "characters": out}


# --------------------------------------------------------------- 点击埋点
class WorldClickIn(BaseModel):
    """世界点击埋点入参。

    novel 允许缺省（保持旧的 400「缺少 novel」语义），但类型必须是字符串、
    长度 ≤64：对象/布尔/数组一律 422，避免脏值进统计维度。
    """
    novel: Optional[str] = Field(default=None, max_length=64)


@router.post("/world-click", summary="记录世界点击")
async def track_world_click(
    payload: WorldClickIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    埋点：用户点开某个世界。

    - **权限**：公开（登录则记录 `user_id`，否则记 IP 并标为游客）
    - **请求体**：`novel`（字符串，≤64 字）；缺字段返回 `400`，类型不对返回 `422`
    - **说明**：只做统计，不校验世界是否真实存在（历史数据兼容）
    """
    novel = (payload.novel or "").strip()
    if not novel:
        raise HTTPException(status_code=400, detail="缺少 novel")
    db.add(
        WorldClickEvent(
            novel=novel[:64],
            user_id=getattr(user, "id", None),
            is_guest=user is None,
            client_ip=client_ip(request),
        )
    )
    await db.commit()
    return {"ok": True}


@router.get("/world-clicks", summary="世界点击排行")
async def world_clicks(db: AsyncSession = Depends(get_db)):
    """
    各世界被点开的次数。

    - **权限**：公开
    - **返回**：近 30 天与累计计数，按累计倒序
    """
    total = dict(
        (await db.execute(
            select(WorldClickEvent.novel, func.count()).group_by(WorldClickEvent.novel)
        )).all()
    )
    cutoff = now_cn() - timedelta(days=30)
    recent = dict(
        (
            await db.execute(
                select(WorldClickEvent.novel, func.count())
                .where(WorldClickEvent.created_at >= cutoff)
                .group_by(WorldClickEvent.novel)
            )
        ).all()
    )
    return {
        "total": sorted(
            [
                {"novel": k, "clicks": v, "clicks_30d": recent.get(k, 0)}
                for k, v in total.items()
            ],
            key=lambda x: -x["clicks"],
        ),
    }


# --------------------------------------------------------------- 投票
@router.get("/world-votes", summary="世界投票结果")
async def list_world_votes(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    角色/世界投票的当前得票与候选。

    - **权限**：公开
    - **返回**：`candidates[]` 与 `total_votes`
    """
    rows = (
        await db.execute(select(WorldVote.world_name, func.count()).group_by(WorldVote.world_name))
    ).all()
    counts = {name: n for name, n in rows}
    key = _voter_key(request, user)
    mine = {
        v.world_name
        for v in (
            await db.execute(select(WorldVote).where(WorldVote.voter_key == key))
        ).scalars().all()
    }
    items = [
        {**c, "votes": counts.get(c["name"], 0), "voted": c["name"] in mine}
        for c in VOTE_CANDIDATES
    ]
    items.sort(key=lambda x: -x["votes"])
    return {"candidates": items, "my_votes": sorted(mine), "total_votes": sum(counts.values())}


@router.post("/world-vote", summary="给世界投票")
async def vote_world(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    投票（同一身份重复投同一项只记一次）。

    - **权限**：公开
    - **请求体**：`novel`
    - **错误**：`400` 参数缺失；`429` 投票过于频繁
    """
    name = (payload or {}).get("world_name")
    if not name or name not in {c["name"] for c in VOTE_CANDIDATES}:
        raise HTTPException(status_code=400, detail="不在候选列表里")
    key = _voter_key(request, user)
    exists = (
        await db.execute(
            select(WorldVote).where(WorldVote.voter_key == key, WorldVote.world_name == name)
        )
    ).scalar_one_or_none()
    if exists:
        await db.delete(exists)
        await db.commit()
        return {"ok": True, "voted": False}
    db.add(WorldVote(world_name=name, user_id=getattr(user, "id", None), voter_key=key))
    await db.commit()
    return {"ok": True, "voted": True}


# --------------------------------------------------------------- 天梯
@router.get("/ladder", summary="天梯榜")
async def ladder(
    world: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    按世界统计最高分 / 平均分 / 参与人数，并给出各世界的高分存档。

    - **权限**：公开（带登录态时会给自己的记录打 `is_me`）
    - **玩家名**：只返回昵称（未设置时兜底为「闯关者 + 用户 id」），**不返回邮箱和手机号**
    - **注意**：返回的高分存档 id 只能看到「积分/成就」摘要；直接读存档详情仍受归属校验（`403`）
    """
    limit = max(1, min(limit, 100))
    q = select(
        GameSession.novel,
        func.count(GameSession.id).label("sessions"),
        func.count(func.distinct(GameSession.user_id)).label("players"),
        func.max(GameSession.points).label("top_points"),
        func.avg(GameSession.points).label("avg_points"),
    ).group_by(GameSession.novel)
    worlds = [
        {
            "novel": r.novel,
            "sessions": int(r.sessions),
            "players": int(r.players),
            "top_points": int(r.top_points or 0),
            "avg_points": round(float(r.avg_points or 0), 1),
        }
        for r in (await db.execute(q)).all()
    ]
    worlds.sort(key=lambda x: (-x["top_points"], -x["sessions"]))

    tq = (
        select(GameSession, User.id, User.nickname)
        .outerjoin(User, User.id == GameSession.user_id)
        .order_by(desc(GameSession.points), desc(GameSession.updated_at))
    )
    if world and world not in ("", "all"):
        tq = tq.where(GameSession.novel == world)
    tq = tq.limit(limit)

    def display_name(user_id, nickname) -> str:
        # 老用户注册时没有昵称：用「闯关者 + 四位 id」兜底，稳定且不含个人信息
        if user_id is None:
            return "游客"
        return nickname or f"闯关者{user_id:04d}"

    top = [
        {
            "rank": i + 1,
            "session_id": s.id,
            "player": display_name(uid, nick),
            "is_guest": uid is None,
            "is_me": bool(current_user and uid == current_user.id),
            "character_name": s.character_name,
            "character_rank": s.character_rank,
            "novel": s.novel,
            "timeline": s.timeline,
            "points": s.points,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for i, (s, uid, nick) in enumerate((await db.execute(tq)).all())
    ]
    return {"worlds": worlds, "top": top, "world": world or "all"}
