#!/usr/bin/env python3
"""
给预设角色批量生成头像（qwen-image-3.0）

    /opt/venv/bin/python scripts/gen_portraits.py --worlds 红楼梦 封神演义 --limit 5 --dry-run
    /opt/venv/bin/python scripts/gen_portraits.py --worlds 红楼梦 封神演义
    /opt/venv/bin/python scripts/gen_portraits.py --worlds 红楼梦 --install   # 写 webp + 回填 JSON

产物：
    ~/.cache/simcrossing/portraits/<世界>/<角色>.png   原图（1140×1472，3:4）
    frontend/public/images/characters/<世界>/<角色>.webp   400×516 网页用
    content/worlds/<世界>.json 里写入 "image": "/images/characters/...webp"

装完记得跑一次：
    /opt/venv/bin/python scripts/import_content.py import --dir content/worlds
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORLDS_DIR = REPO / "content" / "worlds"
# 输出放在仓库外：仓库目录会被 chown 给 www-data，脚本就写不进去了
OUT_DIR = Path.home() / ".cache" / "simcrossing" / "portraits"
PUBLIC_DIR = REPO / "frontend" / "public" / "images" / "characters"

MODEL = os.environ.get("QWEN_IMAGE_MODEL", "qwen-image-3.0")
BASE = "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
SIZE = "1140*1472"

STYLE = {
    "红楼梦": "清代贵族府邸氛围，织锦与木构，烛光与窗纸的柔光",
    "封神演义": "商周神话氛围，青铜器与玄色旗帜，雷电与烽烟",
    "武侠江湖": "明代江湖氛围，粗布衣与旧刀剑，雨夜与灯火",
    "仙侠修真": "东方修仙氛围，云气与灵光，简素道袍",
    "大唐长安·天宝末年": "盛唐长安氛围，胡风织物与金饰，暖色斜阳",
    "北宋汴京之变": "北宋市井氛围，青灰与暖褐，绢帛与木构",
    "三国演义": "汉末三国氛围，甲胄与麻布，风沙与营帐",
    "水浒传": "宋代江湖氛围，粗布短打，山野与酒肆",
    "西游记": "神话取经氛围，云气与山石，僧衣与兽纹",
    "金瓶梅": "明代市井宅院氛围，绸缎与烛影",
    "明代": "明代官场氛围，织金与乌纱",
    "清代": "清代宫廷氛围，石青与绛红",
    "废土末世": "废土末日氛围，锈铁与防尘布，尘霾逆光",
    "都市霸总": "当代都市商战氛围，写字楼玻璃幕墙与夜色霓虹，剪裁利落的西装与衬衫",
    "都市修真": "当代都市修真氛围，写字楼与霓虹背后的灵气微光，通勤装与旧道袍混搭",
    "日常生活": "当代中国城市日常氛围，地铁站、出租屋与便利店灯光，普通的日常穿着",
}

# 现代题材：negative 里必须反过来压古装，不然会画出穿汉服的 CEO
MODERN_WORLDS = {"都市霸总", "都市修真", "日常生活"}
NEG_MODERN = (
    "text, letters, watermark, logo, signature, UI, frame, border, cartoon, anime, "
    "cel shading, oversaturated, lowres, jpeg artifacts, blurry, deformed face, extra limbs, "
    "duplicate subject, hanfu, ancient chinese clothing, armor, palace, swordsman, "
    "historical costume, plastic skin"
)

NEG = (
    "text, letters, watermark, logo, signature, UI, frame, border, cartoon, anime, "
    "cel shading, oversaturated, lowres, jpeg artifacts, blurry, deformed face, extra limbs, "
    "duplicate subject, modern clothing, modern logo, plastic skin"
)


def load_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if key:
        return key
    env = REPO / "backend" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("没有 DASHSCOPE_API_KEY（环境变量或 backend/.env）")


def build_prompt(world: str, ch: dict) -> str:
    style = STYLE.get(world, "东方古典氛围，写实电影质感")
    traits = {
        "minor": "像是街头随时会遇见的人，衣着朴素，神情里有一点局促",
        "main": "气质鲜明，眼神有故事",
    }.get("minor" if ch.get("role") == "minor" else "main")
    bg = (ch.get("background") or "").strip().rstrip("。")
    # 原著里不少角色是少年，但不去生成未成年人的人像：统一按成年形象出图
    age = int(ch.get("age") or 20)
    age_txt = f"{age}岁" if age >= 18 else "二十岁上下的青年"

    return (
        f"{style}。人物半身肖像，{ch.get('name')}，{ch.get('gender') or ''}，{age_txt}，"
        f"身份是{ch.get('rank') or '普通人'}。{traits}。"
        + (f"人物线索：{bg[:60]}。" if bg else "")
        + "侧前方柔光打在脸上，背景虚化，暗部保留细节，低饱和，35mm 电影人像质感，浅景深，"
        "构图胸部以上，人物居中偏左，视线不看镜头。不要出现任何文字、水印、logo。"
    )


def request_image(key: str, prompt: str, size: str, neg: str = NEG) -> bytes:
    body = {
        "model": MODEL,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {
            "prompt_extend": True,
            "size": size,
            "negative_prompt": neg,
            "watermark": False,
        },
    }
    req = urllib.request.Request(
        BASE,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode())
    url = data["output"]["choices"][0]["message"]["content"][0]["image"]
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    with urllib.request.urlopen(url, timeout=180) as r:
        return r.read()


def gen_one(key: str, world: str, ch: dict, force: bool) -> tuple[str, str, float]:
    dst = OUT_DIR / world / f"{ch['name']}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        return ("skip", ch["name"], 0.0)
    prompt = build_prompt(world, ch)
    last_err = None
    for attempt in range(3):
        t0 = time.time()
        try:
            blob = request_image(key, prompt, SIZE, NEG_MODERN if world in MODERN_WORLDS else NEG)
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(blob)
            tmp.replace(dst)
            return ("ok", ch["name"], time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(3 * (attempt + 1))
    return ("fail", f"{ch['name']} ({last_err})", 0.0)


def install(world: str, characters: list[dict]) -> int:
    from PIL import Image

    n = 0
    for ch in characters:
        src = OUT_DIR / world / f"{ch['name']}.png"
        if not src.exists():
            continue
        out_dir = PUBLIC_DIR / world
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / f"{ch['name']}.webp"
        with Image.open(src) as im:
            im.convert("RGB").resize((400, 516), Image.LANCZOS).save(dst, "WEBP", quality=82)
        n += 1
    return n


def write_json(world: str, characters: list[dict]) -> int:
    path = WORLDS_DIR / f"{world}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = 0
    for ch in data["characters"]:
        f = PUBLIC_DIR / world / f"{ch['name']}.webp"
        if f.exists():
            rel = f"/images/characters/{world}/{ch['name']}.webp"
            if ch.get("image") != rel:
                ch["image"] = rel
                updated += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def main() -> None:
    ap = argparse.ArgumentParser(description="批量生成角色头像")
    ap.add_argument("--worlds", nargs="*", default=[], help="世界名（默认全部）")
    ap.add_argument("--limit", type=int, default=0, help="每个世界最多生成几个")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--force", action="store_true", help="已存在也重画")
    ap.add_argument("--install", action="store_true", help="生成后压 webp 并回填 JSON")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    worlds = args.worlds or [p.stem for p in sorted(WORLDS_DIR.glob("*.json"))]
    key = "" if args.dry_run else load_key()

    jobs: list[tuple[str, dict]] = []
    for w in worlds:
        path = WORLDS_DIR / f"{w}.json"
        if not path.exists():
            print(f"  跳过（没有 {w}.json）")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        chars = data["characters"][: args.limit or None]
        for ch in chars:
            jobs.append((w, ch))

    print(f"共 {len(jobs)} 个角色 | 世界 {len(worlds)} 个 | 尺寸 {SIZE} | 并发 {args.concurrency}")
    if args.dry_run:
        for w, ch in jobs[:5]:
            print(f"\n[{w}/{ch['name']}]\n{build_prompt(w, ch)}")
        print(f"\n（dry-run，不请求；共 {len(jobs)} 条）")
        return

    lock = threading.Lock()
    done = {"ok": 0, "skip": 0, "fail": 0}
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(gen_one, key, w, ch, args.force) for w, ch in jobs]
        for fut in as_completed(futures):
            status, name, sec = fut.result()
            with lock:
                done[status] += 1
            icon = {"ok": "✓", "skip": "·", "fail": "✗"}[status]
            print(f"  {icon} {name}" + (f"  {sec:.1f}s" if status == "ok" else ""))

    print(f"\n生成：成功 {done['ok']}，跳过 {done['skip']}，失败 {done['fail']}，用时 {time.time()-t_start:.0f}s")

    if args.install:
        for w in worlds:
            path = WORLDS_DIR / f"{w}.json"
            if not path.exists():
                continue
            chars = json.loads(path.read_text(encoding="utf-8"))["characters"]
            n = install(w, chars)
            m = write_json(w, chars)
            print(f"  {w}: 装 {n} 张 webp，回填 {m} 条 image 字段")
        print("\n下一步：/opt/venv/bin/python scripts/import_content.py import --dir content/worlds")


if __name__ == "__main__":
    main()
