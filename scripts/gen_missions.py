"""给世界包里的角色批量生成使命（mission）。

用法：
    python scripts/gen_missions.py --world 红楼梦          # 只做某个世界
    python scripts/gen_missions.py --all                    # 所有还没有使命的世界
    python scripts/gen_missions.py --all --dry-run          # 只统计

规则：
- 一个角色一次调用，产出它所有时间节点的使命（同一角色跨时间线更连贯）。
- 已有 mission 的时间节点会跳过，可安全重跑（断点续跑）。
- 校验不过会重试，最终仍失败就把该角色记到 failed 计数，不影响其他角色。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORLDS_DIR = REPO / "content" / "worlds"

sys.path.insert(0, str(REPO / "backend"))


SYSTEM = """你是互动小说的关卡设计师。给定一个世界、一个角色，以及这个角色所处的几个时间节点，
请为每个时间节点设计一条「使命」——它是这一局游戏的主线目标，用来防止剧情无限飘向支线细节。

设计原则：
1. 使命必须小、具体、有期限、有赌注。不要写成"匡扶汉室""拯救苍生"这种空话。
2. 三个阶段要能一步步做出来：拿到某样东西、说服某个人、走到某个地方、在某个时间点之前完成。
3. 赌注要具体到人和物：谁活不下来、什么会被烧掉、什么机会永远消失。
4. 角色如果是小人物（差役、丫鬟、伙计、散兵），使命应当更小、更私人，像普通人的处境。
5. 同一角色的不同时间节点，使命要随局势变化，不要重复同一个目标。

只输出 JSON，不要解释，格式：
{"<时间节点名>": {"title": "≤12字", "goal": "20-40字，一句话说清要做什么、期限是什么",
  "stages": [{"name": "≤12字", "detail": "≤24字，怎么做"}, ... 共3个 ...],
  "deadline_turns": 12, "stakes": "15-30字，失败的后果"}, ...}
"""


def build_prompt(world: dict, ch: dict, only=None) -> str:
    tl_lines = []
    for name, det in ch["timelines"].items():
        if only and name not in only:
            continue
        bg = (det.get("background") or "").strip()
        scene = (det.get("initial_scene") or "").strip()
        tl_lines.append(f"### {name}\n背景：{bg[:400]}\n开场：{scene[:200]}")

    return f"""世界：{world.get('novel') or world.get('name', '')}（{world.get('description', '')[:120]}）

角色：{ch['name']}，{ch['rank']}，{ch.get('age', '')}岁，{ch.get('gender', '')}
角色背景：{(ch.get('background') or '')[:300]}
{'（这是个小人物角色，使命要小而具体）' if ch.get('is_minor') else ''}

时间节点与处境：
{chr(10).join(tl_lines)}

请为以上 {len([t for t in ch['timelines'] if not only or t in only])} 个时间节点各设计一条使命，严格按 JSON 输出，键名必须与上面时间节点名完全一致。"""


def parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def clean_mission(m: dict):
    if not isinstance(m, dict):
        return None
    title = str(m.get("title") or "").strip()[:20]
    goal = str(m.get("goal") or "").strip()[:80]
    stakes = str(m.get("stakes") or "").strip()[:60]
    stages = m.get("stages") or []
    if not (title and goal and stakes) or not isinstance(stages, list) or len(stages) < 2:
        return None
    cleaned = []
    for st in stages[:3]:
        if not isinstance(st, dict):
            continue
        name = str(st.get("name") or "").strip()[:20]
        detail = str(st.get("detail") or "").strip()[:40]
        if name:
            cleaned.append({"name": name, "detail": detail})
    if len(cleaned) < 2:
        return None
    return {
        "title": title,
        "goal": goal,
        "stages": cleaned,
        "deadline_turns": 12,
        "stakes": stakes,
    }


async def gen_for_world(world_path: Path, provider, sem: asyncio.Semaphore, dry: bool) -> dict:
    from app.core.config import settings

    data = json.loads(world_path.read_text(encoding="utf-8"))
    todo = []
    for ch in data["characters"]:
        missing = [tl for tl, det in ch["timelines"].items() if not det.get("mission")]
        if missing:
            todo.append((ch, missing))

    stats = {"world": world_path.stem, "chars": len(todo), "ok": 0, "fail": 0}
    if dry or not todo:
        return stats

    lock = asyncio.Lock()

    async def one(ch, missing):
        async with sem:
            prompt = build_prompt(data, ch)
            for attempt in (1, 2):
                try:
                    resp = await provider._acreate(
                        model=settings.DEEPSEEK_MODEL,
                        messages=[
                            {"role": "system", "content": SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.85,
                        max_tokens=2600,
                        timeout=120,
                        extra_body={"thinking": {"type": "disabled"}},
                    )
                    parsed = parse_json(resp.choices[0].message.content or "")
                    if not parsed:
                        raise ValueError("bad json")
                    got = 0
                    async with lock:
                        for tl in missing:
                            mission = clean_mission(parsed.get(tl))
                            if mission:
                                ch["timelines"][tl]["mission"] = mission
                                got += 1
                        stats["ok"] += got
                    if got == 0:
                        raise ValueError("no valid mission")
                    print(f"  ✓ {ch['name']}：{got}/{len(missing)}", flush=True)
                    return
                except Exception as e:
                    if attempt == 2:
                        # 整批 JSON 坏了（常见于节点太多被截断）：逐个节点重来
                        got = 0
                        for tl in missing:
                            try:
                                r2 = await provider._acreate(
                                    model=settings.DEEPSEEK_MODEL,
                                    messages=[
                                        {"role": "system", "content": SYSTEM},
                                        {"role": "user", "content": build_prompt(data, ch, only=[tl])},
                                    ],
                                    temperature=0.85,
                                    max_tokens=900,
                                    timeout=90,
                                    extra_body={"thinking": {"type": "disabled"}},
                                )
                                single = parse_json(r2.choices[0].message.content or "")
                                cm = clean_mission((single or {}).get(tl))
                                if cm:
                                    async with lock:
                                        ch["timelines"][tl]["mission"] = cm
                                        stats["ok"] += 1
                                    got += 1
                            except Exception:
                                pass
                        if got:
                            print(f"  ✓ {ch['name']}：逐节点补 {got}/{len(missing)}", flush=True)
                        else:
                            async with lock:
                                stats["fail"] += 1
                            print(f"  ✗ {ch['name']}：{type(e).__name__} {str(e)[:80]}", flush=True)
                    else:
                        await asyncio.sleep(1.5)

    await asyncio.gather(*[one(ch, missing) for ch, missing in todo])
    world_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--skip", nargs="*", default=["废土末世"])
    args = ap.parse_args()

    from app.services.game_service import get_provider

    provider = get_provider()
    sem = asyncio.Semaphore(args.concurrency)

    if args.world:
        paths = [WORLDS_DIR / f"{args.world}.json"]
    else:
        paths = sorted(p for p in WORLDS_DIR.glob("*.json") if p.stem not in args.skip)

    total = {"ok": 0, "fail": 0}
    for p in paths:
        if not p.exists():
            print(f"跳过（不存在）：{p.name}")
            continue
        print(f"\n=== {p.stem} ===", flush=True)
        st = await gen_for_world(p, provider, sem, args.dry_run)
        print(f"{st['world']}：待生成角色 {st['chars']}，写入使命 {st['ok']}，失败角色 {st['fail']}", flush=True)
        total["ok"] += st["ok"]
        total["fail"] += st["fail"]

    print(f"\n合计：写入 {total['ok']} 条使命，失败角色 {total['fail']} 个")


if __name__ == "__main__":
    asyncio.run(main())
