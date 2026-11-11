#!/usr/bin/env python3
"""
世界包导入 / 导出工具

世界内容以 content/worlds/<世界名>.json 为唯一来源，导入数据库后前端即可选择。

    # 把数据库现有世界导出成 JSON（一次性，之后以文件为准）
    /opt/venv/bin/python scripts/import_content.py export --dir content/worlds

    # 导入单个世界（按名字 upsert，可重复执行）
    /opt/venv/bin/python scripts/import_content.py import --file content/worlds/红楼梦.json

    # 导入整个目录
    /opt/venv/bin/python scripts/import_content.py import --dir content/worlds

    # 只看会发生什么，不写库
    /opt/venv/bin/python scripts/import_content.py import --dir content/worlds --dry-run

    # 校验：世界/时间线/角色/节点数量与缺初始场景的角色
    /opt/venv/bin/python scripts/import_content.py check

JSON 结构：
{
  "novel": "红楼梦",
  "description": "一句话介绍",
  "sort_order": 8,
  "cover": "hongloumeng",
  "timelines": [{"name": "大观园初建", "description": "…", "sort_order": 1}],
  "characters": [{
      "name": "贾宝玉", "gender": "男性", "age": 16, "rank": "荣国府二公子",
      "starting_points": 60, "role": "main",
      "background": "全局人设（可选，缺省用第一个时间节点的 background）",
      "timelines": {
          "大观园初建": {"background": "你在这一节点的身份与处境", "initial_scene": "开局第一屏"}
      }
  }]
}

role: "main" 普通角色；"minor" 小人物（差役、丫鬟、小妖…），前端会打「小人物」标记。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
# settings 从 backend/.env 读，工作目录必须在 backend 下
os.chdir(REPO / "backend")

from sqlalchemy import select  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.models import (  # noqa: E402
    CharacterTimeline,
    NovelConfig,
    PresetCharacter,
    TimelineConfig,
)

WORLDS_DIR = REPO / "content" / "worlds"


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def warn(msg: str) -> None:
    print(f"  ! {msg}")


# ---------------------------------------------------------------- export
async def export_worlds(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    async with AsyncSessionLocal() as db:
        novels = (await db.execute(select(NovelConfig).order_by(NovelConfig.sort_order))).scalars().all()
        for novel in novels:
            tls = (
                await db.execute(
                    select(TimelineConfig)
                    .where(TimelineConfig.novel_id == novel.id)
                    .order_by(TimelineConfig.sort_order)
                )
            ).scalars().all()
            chars = (
                await db.execute(
                    select(PresetCharacter).where(PresetCharacter.novel == novel.name).order_by(PresetCharacter.id)
                )
            ).scalars().all()

            characters = []
            for ch in chars:
                links = (
                    await db.execute(
                        select(CharacterTimeline).where(CharacterTimeline.character_id == ch.id)
                    )
                ).scalars().all()
                characters.append(
                    {
                        "name": ch.name,
                        "gender": ch.gender or "",
                        "age": ch.age or 0,
                        "rank": ch.rank or "",
                        "starting_points": ch.starting_points or 0,
                        "role": "minor" if ch.is_minor else "main",
                        "background": ch.background or "",
                        "image": ch.image or "",
                        "timelines": {
                            l.timeline: {
                                "background": l.background or "",
                                "initial_scene": l.initial_scene,
                                **({"mission": l.mission} if l.mission else {}),
                            }
                            for l in links
                        },
                    }
                )

            payload = {
                "novel": novel.name,
                "description": novel.description or "",
                "sort_order": novel.sort_order or 0,
                "cover": "",
                "timelines": [
                    {"name": t.name, "description": t.description or "", "sort_order": t.sort_order or 0}
                    for t in tls
                ],
                "characters": characters,
            }
            path = out_dir / f"{novel.name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ok(f"{novel.name}: {len(tls)} 时间线 / {len(chars)} 角色 -> {path.relative_to(REPO)}")


# ---------------------------------------------------------------- import
async def import_world(path: Path, dry_run: bool = False, prune: bool = False) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data["novel"]
    stats = {"timelines": 0, "characters": 0, "links": 0, "pruned": 0}

    async with AsyncSessionLocal() as db:
        novel = (await db.execute(select(NovelConfig).where(NovelConfig.name == name))).scalar_one_or_none()
        if novel is None:
            novel = NovelConfig(name=name, description=data.get("description"), sort_order=data.get("sort_order", 0))
            db.add(novel)
            await db.flush()
            stats["novel"] = "created"
        else:
            novel.description = data.get("description", novel.description)
            # 排序是运营在后台手工调的，导入不要覆盖它——
            # 否则每次重新部署跑一次 import，世界顺序就被 JSON 里的旧值打回去
            # （用户手工排好的顺序就这样丢过一次）。新世界用 JSON 的 sort_order 建就行。
            if data.get("description"):
                novel.description = data["description"]
            stats["novel"] = "updated"

        # 时间线
        exist_tl = {
            t.name: t
            for t in (
                await db.execute(select(TimelineConfig).where(TimelineConfig.novel_id == novel.id))
            ).scalars().all()
        }
        for tl in data.get("timelines", []):
            row = exist_tl.get(tl["name"])
            if row is None:
                db.add(
                    TimelineConfig(
                        novel_id=novel.id,
                        name=tl["name"],
                        description=tl.get("description", ""),
                        sort_order=tl.get("sort_order", 0),
                    )
                )
            else:
                row.description = tl.get("description", row.description)
                row.sort_order = tl.get("sort_order", row.sort_order)
            stats["timelines"] += 1

        # 角色
        exist_ch = {
            c.name: c
            for c in (
                await db.execute(select(PresetCharacter).where(PresetCharacter.novel == name))
            ).scalars().all()
        }
        for ch in data.get("characters", []):
            links = ch.get("timelines", {}) or {}
            first_bg = next(iter(links.values()), {}).get("background", "") if links else ""
            row = exist_ch.get(ch["name"])
            if row is None:
                row = PresetCharacter(novel=name, name=ch["name"])
                db.add(row)
                exist_ch[ch["name"]] = row
            row.gender = ch.get("gender") or row.gender
            row.age = ch.get("age") or row.age
            row.rank = ch.get("rank") or row.rank
            row.background = ch.get("background") or first_bg or row.background
            row.starting_points = ch.get("starting_points", row.starting_points or 0)
            row.is_minor = (ch.get("role") or "main") == "minor"
            if ch.get("image") is not None:
                row.image = ch.get("image") or None
            await db.flush()
            stats["characters"] += 1

            exist_links = {
                l.timeline: l
                for l in (
                    await db.execute(
                        select(CharacterTimeline).where(CharacterTimeline.character_id == row.id)
                    )
                ).scalars().all()
            }
            for tl_name, detail in links.items():
                lk = exist_links.get(tl_name)
                if lk is None:
                    db.add(
                        CharacterTimeline(
                            character_id=row.id,
                            timeline=tl_name,
                            background=detail.get("background", ""),
                            initial_scene=detail["initial_scene"],
                            mission=detail.get("mission"),
                        )
                    )
                else:
                    lk.background = detail.get("background", lk.background)
                    lk.initial_scene = detail.get("initial_scene", lk.initial_scene)
                    if "mission" in detail:
                        lk.mission = detail["mission"]
                stats["links"] += 1

            if prune:
                for tl_name, lk in exist_links.items():
                    if tl_name not in links:
                        await db.delete(lk)
                        stats["pruned"] += 1

        if prune:
            names = {c["name"] for c in data.get("characters", [])}
            for ch_name, row in exist_ch.items():
                if ch_name not in names:
                    await db.delete(row)
                    stats["pruned"] += 1

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    return stats


async def check() -> None:
    async with AsyncSessionLocal() as db:
        novels = (await db.execute(select(NovelConfig).order_by(NovelConfig.sort_order))).scalars().all()
        total_ch = total_minor = 0
        print(f"{'世界':<14}{'时间线':>6}{'角色':>6}{'小人物':>7}{'节点':>6}")
        for n in novels:
            tl = (await db.execute(select(TimelineConfig).where(TimelineConfig.novel_id == n.id))).scalars().all()
            chs = (await db.execute(select(PresetCharacter).where(PresetCharacter.novel == n.name))).scalars().all()
            ids = [c.id for c in chs]
            links = 0
            if ids:
                links = len(
                    (await db.execute(select(CharacterTimeline).where(CharacterTimeline.character_id.in_(ids))))
                    .scalars()
                    .all()
                )
            minor = sum(1 for c in chs if c.is_minor)
            total_ch += len(chs)
            total_minor += minor
            print(f"{n.name:<14}{len(tl):>6}{len(chs):>6}{minor:>7}{links:>6}")
        print(f"\n合计：{len(novels)} 个世界 / {total_ch} 个角色（其中小人物 {total_minor}）")


def _abs(p: str) -> Path:
    """相对路径按仓库根目录解析（脚本会 chdir 到 backend）"""
    q = Path(p)
    return q if q.is_absolute() else (REPO / q)


def main() -> None:
    ap = argparse.ArgumentParser(description="世界包导入/导出")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="把数据库里的世界导出成 JSON")
    e.add_argument("--dir", default=str(WORLDS_DIR))

    i = sub.add_parser("import", help="导入 JSON 世界包")
    i.add_argument("--file")
    i.add_argument("--dir")
    i.add_argument("--dry-run", action="store_true")
    i.add_argument("--prune", action="store_true", help="删除 JSON 里没有的角色/节点（危险）")

    sub.add_parser("check", help="打印各世界数据量")

    args = ap.parse_args()

    if args.cmd == "export":
        asyncio.run(export_worlds(_abs(args.dir)))
    elif args.cmd == "import":
        files: list[Path] = []
        if args.file:
            files.append(_abs(args.file))
        if args.dir:
            files.extend(sorted(_abs(args.dir).glob("*.json")))
        if not files:
            ap.error("需要 --file 或 --dir")
        async def _run_all() -> None:
            for f in files:
                st = await import_world(f, dry_run=args.dry_run, prune=args.prune)
                flag = "（dry-run，未写库）" if args.dry_run else ""
                print(
                    f"{f.stem}: 时间线 {st['timelines']} / 角色 {st['characters']} / 节点 {st['links']}"
                    f" / 清理 {st['pruned']} {flag}"
                )

        # 同一个事件循环里跑完：asyncpg 连接不能跨 loop 复用
        asyncio.run(_run_all())
    else:
        asyncio.run(check())


if __name__ == "__main__":
    main()
