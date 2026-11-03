"""社区功能：世界卡点击埋点、想看世界的投票、天梯排行榜"""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import (
    CharacterTimeline,
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
@router.get("/world/{novel}/characters")
async def list_world_characters(novel: str, db: AsyncSession = Depends(get_db)):
    """某个世界的全部预设角色（含小人物、头像、可玩时间节点）。

    角色优先、时间其次：前端先用它渲染角色卡片，选中角色后再展示可用节点。
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
@router.post("/world-click")
async def track_world_click(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    novel = (payload or {}).get("novel")
    if not novel:
        raise HTTPException(status_code=400, detail="缺少 novel")
    db.add(
        WorldClickEvent(
            novel=str(novel)[:64],
            user_id=getattr(user, "id", None),
            is_guest=user is None,
            client_ip=client_ip(request),
        )
    )
    await db.commit()
    return {"ok": True}


@router.get("/world-clicks")
async def world_clicks(db: AsyncSession = Depends(get_db)):
    """各世界被点开的次数（近 30 天 + 累计）"""
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
@router.get("/world-votes")
async def list_world_votes(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
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


@router.post("/world-vote")
async def vote_world(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
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
@router.get("/ladder")
async def ladder(world: Optional[str] = None, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """天梯榜：按世界统计最高分/平均分/参与人数，并给出各世界的高分存档"""
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

    tq = select(GameSession).order_by(desc(GameSession.points), desc(GameSession.updated_at))
    if world and world not in ("", "all"):
        tq = tq.where(GameSession.novel == world)
    tq = tq.limit(limit)
    top = [
        {
            "rank": i + 1,
            "session_id": s.id,
            "character_name": s.character_name,
            "character_rank": s.character_rank,
            "novel": s.novel,
            "timeline": s.timeline,
            "points": s.points,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for i, s in enumerate((await db.execute(tq)).scalars().all())
    ]
    return {"worlds": worlds, "top": top, "world": world or "all"}
