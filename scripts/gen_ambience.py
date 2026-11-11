#!/usr/bin/env python3
"""批量生成世界环境音床（qwen-audio-3.1-tts-next）

每个世界一条 20 秒左右的循环底噪，进游戏后低音量循环播放（前端做交叉淡入）。
一次生成、永久复用——运行时零调用成本。

    /opt/venv/bin/python scripts/gen_ambience.py
    /opt/venv/bin/python scripts/gen_ambience.py --only 三国演义 --force
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
OUT_DIR = REPO / "frontend" / "public" / "audio" / "amb"
MANIFEST = REPO / "content" / "ambience.json"

MODEL = "qwen-audio-3.1-tts-next"
URL = (
    "https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com"
    "/api/v1/services/audio/tts/SpeechSynthesizer"
)
STYLE = "环境音，无人声、无音乐、无旁白，自然的环境底噪，音量平稳没有突然的峰值"


def load_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if key:
        return key
    env = REPO / "backend" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("没有 DASHSCOPE_API_KEY")


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
    with urllib.request.urlopen(data["output"]["audio"]["url"], timeout=180) as resp:
        return resp.read()


def to_mp3(wav_bytes: bytes, dst: Path) -> float:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_path,
             # 统一响度：不同世界的底噪原始电平差很多，不归一会有的世界几乎听不见
             "-af", "loudnorm=I=-18:TP=-2:LRA=9",
             "-ac", "1", "-ar", "24000", "-b:a", "64k", str(dst)],
            check=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip() or 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    items = json.loads((REPO / "scripts/prompts/ambience.json").read_text(encoding="utf-8"))
    if args.only:
        items = [i for i in items if i["novel"] in args.only]

    key = load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    lock = threading.Lock()
    stats = {"ok": 0, "skip": 0, "fail": 0}
    t0 = time.time()

    def job(item: dict):
        dst = OUT_DIR / f"{item['name']}.mp3"
        if dst.exists() and not args.force:
            return ("skip", item, dst.stat().st_size, 0.0)
        wav = synth(key, f"{STYLE}。{item['prompt']}")
        dur = to_mp3(wav, dst)
        return ("ok", item, dst.stat().st_size, dur)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for fut in as_completed([pool.submit(job, it) for it in items]):
            try:
                status, item, size, dur = fut.result()
            except Exception as exc:  # noqa: BLE001
                with lock:
                    stats["fail"] += 1
                print(f"  ✗ {exc}")
                continue
            with lock:
                stats[status] += 1
                if status == "ok":
                    manifest[item["novel"]] = {
                        "file": f"/audio/amb/{item['name']}.mp3",
                        "desc": item["prompt"],
                        "duration": round(dur, 2),
                        "bytes": size,
                    }
            print(f"  {'✓' if status == 'ok' else '·'} {item['novel']}  {size // 1024}KB  {dur:.1f}s")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\n完成：成功 {stats['ok']} 跳过 {stats['skip']} 失败 {stats['fail']}，用时 {time.time()-t0:.0f}s")
    print(f"清单：{MANIFEST}")


if __name__ == "__main__":
    main()
