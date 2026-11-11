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


WORLD_ART = {
    "三国演义": "史诗电影级 CG 厚涂，汉代军营与青铜纹样，营帐旗帜与风沙，暖金侧逆光，厚重笔触与真实金属高光",
    "水浒传": "国风厚涂电影感，山寨木栅与山野水汽薄雾，冷绿土黄对比，笔触明显",
    "红楼梦": "工笔重彩融合油画质感，织锦缎面、点翠珠翠与绒花，烛火与窗棂斑驳光影，柔润细腻",
    "金瓶梅": "明代市井写实油画，绸缎光泽、烛影摇晃、木构宅院，暖褐与朱红，厚重颜料肌理",
    "明代": "明代宫廷人物画风，朱漆宫墙与深色背景，戏剧性侧光，金线与织物细节清晰",
    "清代": "清宫暗红与石青配色，金线刺绣与点翠，阴郁高级感，磨砂颗粒质感与浅景深",
    "西游记": "神话 CG，云气与金箔、妖异色光，宏大氛围，体积光穿透云层",
    "封神演义": "上古神话厚涂，青铜纹样与玄色旗帜，雷火与烽烟，史诗光影与强烈明暗",
    "废土末世": "废土电影质感，锈铁、防尘布与补丁，尘霾逆光，脏旧的高级感，颗粒粗糙",
    "武侠江湖": "水墨与厚涂结合，雨夜灯火、湿衣与旧刀剑，冷蓝暖黄对比，笔触凌厉",
    "仙侠修真": "国风动漫厚涂，云海灵光、飘带与道纹，柔和体积光，粒子微光",
    "大唐长安·天宝末年": "盛唐壁画色彩，胡风织锦与金饰，暖色斜阳，丰腴华丽，笔触奔放",
    "北宋汴京之变": "北宋绢本设色，青灰与暖褐，市井细节丰富，淡雅含蓄，局部暖光",
    "都市霸总": "现代电影感，冷灰蓝基底与暖窗光，高定西装面料纹理清晰，浅景深，克制的戏剧光",
    "都市修真": "赛博水墨美学，靛蓝与朱砂渐变的体积光，霓虹与灵气交织，粒子发光消散",
    "日常生活": "当代纪实电影感，自然光与真实城市背景，色彩克制，皮肤质感真实",
}

# 服饰/行头：按身份关键词匹配，越靠前优先级越高。
# 用户反馈「人人一口素衣」——制服、甲胄、补服、凤冠这些是角色的第一眼信息，必须写死。
ANCIENT_ATTIRE = [
    (
        r"皇帝|天子|陛下|帝王|圣上",
        "身穿明黄织金龙袍，五爪龙纹与十二章纹清晰可辨，头戴冕冠或翼善冠，腰束玉带，胸前朝珠，衣料有厚重织金与刺绣的立体光泽",
    ),
    (
        r"太后|皇后|娘娘|贵妃|妃|贵人|公主|格格",
        "身着明黄或石青的朝袍/氅衣，袖口与襟边满绣金线龙纹与海水江崖，头戴点翠凤冠或钿子、东珠流苏，颈挂朝珠，"
        "双手入画戴着金护甲（指甲套），衣料是厚重缎面提花，光下有细密金线反光",
    ),
    (
        r"将军|都督|头领|统领|提辖|校尉|都统|大将|元帅|先锋|女将|飞将|马军|步军|武师|刀客|剑客|镖头|捕快|教头|头目|寨主",
        "身披实战甲胄：札甲或鳞甲片片相接，肩头兽纹吞口，胸护心镜，腰束革带，外罩战袍，腕上护臂，甲片边缘有磨损与冷光",
    ),
    (
        r"丞相|尚书|侍郎|御史|知府|知县|县令|太守|中书|大学士|判官|主簿|幕僚|参军|刺史|督抚|钦差|太监|宦官|内侍|军师",
        "身穿圆领官袍，胸前补子绣禽兽纹样，腰束玉带，头戴乌纱幞头或官帽，袖口与领缘有织金滚边",
    ),
    (
        r"僧人|和尚|法师|长老|道士|道姑|尼|真人|天师",
        "身披僧衣袈裟或素色道袍，布料粗粝有垂坠感，腰间系带，手持念珠或拂尘，头面清净无多余饰物",
    ),
    (
        r"夫人|妾|娘子|姑娘|小姐|佳人|名妓|歌伎|丫鬟|侍女|婆婆|媳妇|妇人",
        "身着袄裙或褙子，外披轻纱披帛，发间簪钗步摇与珠花，衣料是暗纹缎面，袖口绣花，妆面精致",
    ),
    (
        r"书生|秀才|举人|诗人|词人|文士|画师|先生|公子|少爷|学子",
        "身着素色长衫或直裰，腰系丝绦，头戴方巾，手持折扇或书卷，衣料是细麻与绢，褶皱自然",
    ),
    (
        r"商贾|掌柜|员外|财主|富商|老板|东家",
        "身穿绸缎长袍与马褂，指上玉扳指，腰间挂着算盘或钱袋，衣料光泽明显，气派但不过分张扬",
    ),
    (
        r"农夫|渔夫|樵夫|猎户|船夫|伙计|小厮|乞丐|脚夫|更夫|屠户|脚力|杂役|挑夫|车夫",
        "身穿粗布短褐，衣料磨旧有补丁与泥点，袖口卷起，腰间系草绳，肩上搭着汗巾，皮肤有风吹日晒的粗糙质感",
    ),
]

MODERN_ATTIRE = [
    (
        r"总裁|董事|CEO|创始人|董事长|老板|投资人",
        "身着剪裁利落的高定深色西装三件套，衬衫领口挺括，袖扣与腕表考究，面料有细密织纹",
    ),
    (
        r"律师|法务|顾问|总监|经理|主管|特助|助理",
        "身着合体西装或西装裙，内搭衬衫，手里拿着文件夹或平板，衣料平整，气质干练",
    ),
    (
        r"记者|编辑|设计师|策划|创意",
        "身着质感针织衫或休闲西装，搭配简洁配饰，衣着有个人风格但不夸张",
    ),
    (
        r"程序员|工程师|开发|运维|测试|职员|员工",
        "身着衬衫或连帽卫衣，颈上挂着工牌，肩背电脑包，衣着舒适日常",
    ),
    (
        r"医生|护士|教师|老师",
        "身着白大褂或职业套装，内搭衬衫，口袋插着笔，整洁克制",
    ),
    (
        r"学生|大学生|研究生",
        "身着卫衣或校服外套，背着双肩包，衣着青春随意",
    ),
    (
        r"店主|小老板|房东|快递|外卖|保安|司机|工人",
        "身着工作便装，围裙或制服，袖口有使用痕迹，衣着朴素实用",
    ),
]

SIGNATURE_PROPS = [
    (r"青龙偃月刀|关刀", "身旁斜倚一柄青龙偃月刀，刀身冷光"),
    (r"方天画戟", "手中握着方天画戟，戟刃反光"),
    (r"蛇矛|丈八", "手中长矛，矛尖缠着红缨"),
    (r"羽扇|军师", "指间一柄白羽扇"),
    (r"双刀|两把刀", "腰间挂着两把短刀"),
    (r"弓|箭", "肩上背着弓与箭囊"),
    (r"酒|醉", "手边一只酒碗"),
    (r"琴|琵琶|曲", "身旁放着一把琴"),
    (r"药|医", "手边放着药箱与瓷瓶"),
    (r"账|算盘|生意", "手里拨着算盘"),
    (r"书|诗|词|文章", "手握书卷，指节沾一点墨"),
    (r"剑", "腰间佩剑，剑穗微垂"),
    (r"刀", "手边一柄带鞘长刀"),
]


def infer_attire(world: str, ch: dict) -> str:
    rank = ch.get("rank") or ""
    bg = ch.get("background") or ""
    blob = f"{rank} {bg[:80]}"
    table = MODERN_ATTIRE if world in MODERN_WORLDS else ANCIENT_ATTIRE
    for pattern, text in table:
        if re.search(pattern, blob):
            return text
    if world in MODERN_WORLDS:
        return "身着干净利落的日常装束，衬衫或针织外层，面料质感清晰"
    return "身着与身份相称的时代常服，衣料有织物纹理与自然褶皱，配饰克制"


def infer_props(world: str, ch: dict) -> str:
    if world in MODERN_WORLDS:
        return ""
    blob = ((ch.get("rank") or "") + " " + (ch.get("background") or "")[:80])
    for pattern, text in SIGNATURE_PROPS:
        if re.search(pattern, blob):
            return text
    return ""


def negative_for(world: str, ch: dict) -> str:
    base = NEG_MODERN if world in MODERN_WORLDS else NEG
    if world in MODERN_WORLDS:
        return base
    rank_bg = f"{ch.get('rank') or ''} {ch.get('background') or ''}"[:80]
    military = bool(re.search(
        r"将军|都督|头领|统领|提辖|校尉|都统|大将|元帅|先锋|女将|飞将|马军|步军|武师|刀客|剑客|镖头|捕快|教头|寨主", rank_bg))
    royal = bool(re.search(r"皇帝|天子|陛下|帝王|圣上|太后|皇后|娘娘|贵妃|妃|贵人|公主|格格", ch.get("rank") or ""))
    if not military:
        base += ", armor, plate armor, pauldron, helmet, chainmail, shoulder guard"
    if royal:
        base += ", plain dark robe, black robe, simple cloth"
    return base


def build_prompt(world: str, ch: dict) -> str:
    art = WORLD_ART.get(world, "东方古典氛围，电影级 CG 厚涂，真实光影，笔触可见")
    attire = infer_attire(world, ch)
    prop = infer_props(world, ch)
    minor = ch.get("role") == "minor"
    mood = (
        "神态有一点局促与疲惫，是生活里真实的人"
        if minor
        else "眼神有故事，姿态放松但有气场"
    )
    bg = (ch.get("background") or "").strip().rstrip("。")
    age = int(ch.get("age") or 20)
    age_txt = f"{age}岁" if age >= 18 else "二十岁上下的青年"

    royal = bool(re.search(r"皇帝|天子|陛下|帝王|圣上|太后|皇后|娘娘|贵妃|妃|贵人|公主|格格", ch.get("rank") or ""))
    parts = [
        f"风格：{art}。",
        f"服饰：{attire}。",
        (f"道具：{prop}。" if prop else ""),
        f"人物：半身肖像，{ch.get('name')}，{ch.get('gender') or ''}，{age_txt}，身份是{ch.get('rank') or '普通人'}；{mood}。",
        (f"线索：{bg[:60]}。" if bg else ""),
        "构图到腰部，能看清服饰的纹样、材质与配饰；" + ("双手入画，手指与袖口细节清晰；" if royal else "") + "侧前方一束光打在脸上，形成明暗对比，",
        "背景虚化但保留环境信息，浅景深，35mm，真实光影与细腻质感，画面高级不廉价。",
        "不要出现任何文字、水印、logo、边框。",
    ]
    return "".join(p for p in parts if p)


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
            blob = request_image(key, prompt, SIZE, negative_for(world, ch))
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
    ap.add_argument("--characters", nargs="*", default=[], help="只跑指定角色名")
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
        if args.characters:
            chars = [c for c in chars if c["name"] in args.characters]
        for ch in chars:
            jobs.append((w, ch))

    print(f"共 {len(jobs)} 个角色 | 世界 {len(worlds)} 个 | 尺寸 {SIZE} | 并发 {args.concurrency}")
    if args.dry_run:
        for w, ch in jobs[:8]:
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
