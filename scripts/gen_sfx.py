#!/usr/bin/env python3
"""批量生成游戏音效（qwen-audio-3.1-tts-next）

一次生成 wav → ffmpeg 转 64kbps 单声道 mp3 → 落到 frontend/public/audio/sfx/。
音效按「事件名」命名，运行时用 text-embedding 匹配剧情文本（与场景图同一套思路）。

用法：
    python scripts/gen_sfx.py --prompts scripts/prompts/sfx.json --concurrency 2
    python scripts/gen_sfx.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "frontend" / "public" / "audio" / "sfx"
MANIFEST = REPO / "content" / "sfx.json"

MODEL = "qwen-audio-3.1-tts-next"
URL = (
    "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com"
    "/api/v1/services/audio/tts/SpeechSynthesizer"
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


def synth(key: str, prompt: str) -> bytes:
    body = {"model": MODEL, "input": {"text_prompt": prompt, "format": "wav"}}
    req = urllib.request.Request(
        URL,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    audio_url = data["output"]["audio"]["url"]
    with urllib.request.urlopen(audio_url, timeout=180) as resp:
        return resp.read()


def to_mp3(wav_bytes: bytes, dst: Path) -> float:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_path,
             "-ac", "1", "-ar", "24000", "-b:a", "64k", str(dst)],
            check=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(dst)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip() or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description="批量生成游戏音效")
    ap.add_argument("--prompts", default="scripts/prompts/sfx.json")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.loads((REPO / args.prompts).read_text(encoding="utf-8"))
    items = spec["items"]
    if args.only:
        items = [i for i in items if i["name"] in args.only]

    if args.dry_run:
        for it in items:
            print(f"[{it['name']}] {it['prompt']}  tags={it['tags']}")
        print(f"\n（dry-run，共 {len(items)} 条）")
        return

    key = load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    lock = threading.Lock()
    done = {"ok": 0, "skip": 0, "fail": 0}
    t0 = time.time()

    def job(item: dict):
        dst = OUT_DIR / f"{item['name']}.mp3"
        if dst.exists() and not args.force:
            return ("skip", item, dst.stat().st_size, 0.0, 0.0)
        wav = synth(key, f"{spec['style']}\n{item['prompt']}")
        dur = to_mp3(wav, dst)
        return ("ok", item, dst.stat().st_size, dur, 0.0)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(job, it) for it in items]
        for fut in as_completed(futures):
            try:
                status, item, size, dur, _ = fut.result()
            except Exception as exc:  # noqa: BLE001
                with lock:
                    done["fail"] += 1
                print(f"  ✗ {exc}")
                continue
            with lock:
                done[status] += 1
                if status == "ok":
                    manifest[item["name"]] = {
                        "desc": item["desc"],
                        "tags": item["tags"],
                        "duration": round(dur, 2),
                        "bytes": size,
                    }
            icon = "✓" if status == "ok" else "·"
            print(f"  {icon} {item['name']}  {size // 1024}KB  {dur:.1f}s")

    # 合并进清单（保留已有条目，支持增量补音效）
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\n完成：成功 {done['ok']}，跳过 {done['skip']}，失败 {done['fail']}，用时 {time.time()-t0:.0f}s")
    print(f"清单：{MANIFEST}（{len(manifest)} 条）  音频：{OUT_DIR}")


if __name__ == "__main__":
    main()
