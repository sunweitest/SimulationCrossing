#!/usr/bin/env python3
"""
批量生成配图（阿里云百炼 qwen-image-3.0）

用法：
    cd /opt/novel/SimulationCrossing
    /opt/venv/bin/python scripts/gen_images.py --prompts scripts/prompts/wasteland.json --out /tmp/wasteland
    # 只跑一条试试
    /opt/venv/bin/python scripts/gen_images.py --prompts scripts/prompts/wasteland.json --only 辐射尘中的城市废墟
    # 生成完直接装进项目（场景图 + 封面缩略图）
    /opt/venv/bin/python scripts/gen_images.py --prompts scripts/prompts/wasteland.json --install

说明：
- API Key 依次从环境变量 DASHSCOPE_API_KEY、backend/.env 读取，不会打印出来
- 图片 URL 有时效，生成后立刻下载
- JSON 里 cover_target 指定封面写到 images/<name>.png 与 covers/<name>.webp（默认 wasteland）
- 已存在的文件默认跳过，加 --force 覆盖
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / "backend" / ".env"

# 北京：工作空间 Key 只在北京有效（东京端点用同一个 Key 会报 InvalidApiKey）
DEFAULT_ENDPOINT = (
    "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com"
    "/api/v1/services/aigc/multimodal-generation/generation"
)


def load_api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("找不到 DASHSCOPE_API_KEY：请设置在环境变量或 backend/.env 里")


def build_prompt(item: dict, style: str) -> str:
    prompt = (item.get("prompt") or "").strip()
    if style and style not in prompt:
        prompt = f"{prompt}\n\n{style}"
    return prompt


def call_api(api_key: str, endpoint: str, model: str, prompt: str, size: str,
             negative: str, extend: bool, timeout: int = 300) -> dict:
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"prompt_extend": extend},
    }
    if size:
        payload["parameters"]["size"] = size
    if negative:
        payload["parameters"]["negative_prompt"] = negative

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if body.get("code"):
        raise RuntimeError(f"{body.get('code')}: {body.get('message')}")

    content = body["output"]["choices"][0]["message"]["content"]
    url = next((c.get("image") for c in content if c.get("image")), None)
    if not url:
        raise RuntimeError(f"响应里没有图片地址: {json.dumps(body, ensure_ascii=False)[:300]}")

    return {
        "url": url,
        "request_id": body.get("request_id"),
        "width": body.get("usage", {}).get("output_width"),
        "height": body.get("usage", {}).get("output_height"),
    }


def download(url: str, dest: Path, timeout: int = 180) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(tmp, "wb") as f:
        total = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    tmp.replace(dest)
    return total


def gen_one(item: dict, cfg: dict, out_dir: Path, meta_path: Path) -> dict:
    name = item["name"]
    dest = out_dir / f"{name}.png"
    if dest.exists() and not cfg["force"]:
        return {"name": name, "status": "skip", "file": str(dest)}

    prompt = build_prompt(item, cfg["style"])
    last_err = None
    for attempt in range(1, cfg["retries"] + 1):
        try:
            t0 = time.time()
            result = call_api(cfg["api_key"], cfg["endpoint"], cfg["model"], prompt,
                              cfg["size"], cfg["negative"], cfg["extend"])
            size_bytes = download(result["url"], dest)
            rec = {
                "name": name,
                "status": "ok",
                "file": str(dest),
                "bytes": size_bytes,
                "width": result["width"],
                "height": result["height"],
                "request_id": result["request_id"],
                "seconds": round(time.time() - t0, 1),
                "prompt": prompt,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(meta_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return rec
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            if attempt < cfg["retries"]:
                wait = min(30, 3 * attempt + random.random() * 2)
                print(f"  [{name}] 第 {attempt} 次失败（{last_err}），{wait:.1f}s 后重试", flush=True)
                time.sleep(wait)
    return {"name": name, "status": "fail", "error": last_err}


def install_images(out_dir: Path, items: list, cover_name: str | None,
                  cover_target: str = "wasteland"):
    """把生成结果装进项目：场景图进 public/images/scene，封面进 images/ + covers/"""
    scene_dir = REPO / "frontend" / "public" / "images" / "scene"
    covers_dir = REPO / "frontend" / "public" / "images" / "covers"
    images_dir = REPO / "images"
    for d in (scene_dir, covers_dir, images_dir):
        d.mkdir(parents=True, exist_ok=True)

    copied = []
    for item in items:
        src = out_dir / f"{item['name']}.png"
        if not src.exists():
            continue
        if item.get("kind") == "cover" or item["name"] == cover_name:
            dst = images_dir / f"{item.get('cover_target') or cover_target}.png"
        else:
            dst = scene_dir / f"{item['name']}.png"
        dst.write_bytes(src.read_bytes())
        copied.append(dst)

    cover_targets = sorted({(it.get("cover_target") or cover_target) for it in items if it.get("kind") == "cover"} or {cover_target})
    cover = images_dir / f"{cover_targets[0]}.png"
    for ctarget in cover_targets:
        cover = images_dir / f"{ctarget}.png"
        if not cover.exists():
            continue
        try:
            from PIL import Image

            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            with Image.open(cover) as im:
                im.convert("RGB").resize((400, 225), resample).save(
                    covers_dir / f"{ctarget}.webp", "WEBP", quality=80
                )
            copied.append(covers_dir / f"{ctarget}.webp")
        except ImportError:
            print("提示：没装 Pillow，封面缩略图没生成（uv pip install --python /opt/venv/bin/python pillow）")

    for p in copied:
        print(f"  已安装 {p}")
    print("\n下一步：sudo systemctl restart novel-backend（图片数量变化会自动重建 embedding 缓存）")
    return copied


def main():
    ap = argparse.ArgumentParser(description="批量生成配图（qwen-image-3.0）")
    ap.add_argument("--prompts", required=True, help="提示词 JSON 文件")
    ap.add_argument("--out", default=str(REPO / "scripts" / "out"), help="输出目录")
    ap.add_argument("--only", action="append", help="只生成指定 name（可重复）")
    ap.add_argument("--limit", type=int, help="只生成前 N 条")
    ap.add_argument("--concurrency", type=int, default=2, help="并发数，默认 2")
    ap.add_argument("--retries", type=int, default=3, help="单张重试次数")
    ap.add_argument("--model", default="qwen-image-3.0")
    ap.add_argument("--size", default=None, help="如 1664*928（16:9），默认取 JSON 里的 size")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--force", action="store_true", help="覆盖已存在的图")
    ap.add_argument("--no-extend", action="store_true", help="关闭 prompt_extend（更忠于原文）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做什么，不调用 API")
    ap.add_argument("--install", action="store_true", help="生成后直接装进项目")
    args = ap.parse_args()

    spec = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    items = spec.get("items", [])
    if args.only:
        wanted = set(args.only)
        items = [i for i in items if i["name"] in wanted]
    if args.limit:
        items = items[: args.limit]
    if not items:
        sys.exit("没有匹配的提示词")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.jsonl"

    cfg = {
        "api_key": "" if args.dry_run else load_api_key(),
        "endpoint": args.endpoint,
        "model": args.model,
        "size": args.size or spec.get("size") or "1664*928",
        "negative": spec.get("negative", ""),
        "style": spec.get("style", ""),
        "extend": not args.no_extend,
        "retries": args.retries,
        "force": args.force,
    }

    print(f"共 {len(items)} 张 | 模型 {cfg['model']} | 尺寸 {cfg['size']} | 并发 {args.concurrency} | 输出 {out_dir}")
    if args.dry_run:
        for i in items:
            print(f"  - {i['name']}（{i.get('kind', 'scene')}）{len(build_prompt(i, cfg['style']))} 字")
        return

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(gen_one, i, cfg, out_dir, meta_path): i for i in items}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                rec = fut.result()
            except Exception as e:  # noqa: BLE001
                rec = {"name": item["name"], "status": "fail", "error": str(e)}
            results.append(rec)
            if rec["status"] == "ok":
                print(f"  ✓ {rec['name']}  {rec['width']}x{rec['height']}  "
                      f"{rec['bytes'] / 1024:.0f}KB  {rec['seconds']}s", flush=True)
            elif rec["status"] == "skip":
                print(f"  · {rec['name']} 已存在，跳过", flush=True)
            else:
                print(f"  ✗ {rec['name']} 失败：{rec.get('error')}", flush=True)

    ok = [r for r in results if r["status"] == "ok"]
    skip = [r for r in results if r["status"] == "skip"]
    fail = [r for r in results if r["status"] == "fail"]
    print(f"\n完成：成功 {len(ok)}，跳过 {len(skip)}，失败 {len(fail)}，用时 {time.time() - t0:.0f}s")
    for r in fail:
        print(f"  失败：{r['name']} → {r.get('error')}")

    if args.install and (ok or skip):
        print("\n安装到项目：")
        install_images(out_dir, items, spec.get("cover_name"), spec.get("cover_target", "wasteland"))

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
