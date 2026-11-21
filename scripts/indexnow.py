#!/usr/bin/env python3
"""把更新过的 URL 推给 IndexNow（Bing / Yandex / Seznam 共用协议）

内容一有变化就推一次，搜索引擎不必等下一次爬取。Google 不吃 IndexNow
（靠 sitemap + 自然抓取），但 Bing 系和部分 AI 抓取器会直接用。

    python3 scripts/indexnow.py                 # 推 sitemap 里的全部 URL
    python3 scripts/indexnow.py / /w/bazong.html  # 只推这几条
    python3 scripts/indexnow.py --dry-run

校验文件由 scripts/gen_seo_pages.py 生成在 frontend/public/<key>.txt，
key 存在 content/indexnow_key.txt —— 改了 key 要重新 gen 一次并等线上生效。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = "https://wanchuanyue.com"
HOST = "wanchuanyue.com"
ENDPOINTS = ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]


def load_key() -> str:
    p = REPO / "content" / "indexnow_key.txt"
    if not p.exists():
        sys.exit("没有 content/indexnow_key.txt，先跑 scripts/gen_seo_pages.py")
    return p.read_text(encoding="utf-8").strip()


def sitemap_urls() -> list[str]:
    p = REPO / "frontend" / "public" / "sitemap.xml"
    if not p.exists():
        sys.exit("没有 sitemap.xml，先跑 scripts/gen_seo_pages.py")
    return re.findall(r"<loc>([^<]+)</loc>", p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="要推送的路径（默认推 sitemap 全部）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = load_key()
    urls = [u if u.startswith("http") else f"{SITE}{u if u.startswith('/') else '/' + u}" for u in args.paths] or sitemap_urls()
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{SITE}/{key}.txt",
        "urlList": urls[:10000],
    }
    print(f"IndexNow: {len(urls)} 条 URL → {HOST}")
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:600])
        return

    ok = False
    for endpoint in ENDPOINTS:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
            print(f"  {endpoint} → {code}")
            ok = ok or code in (200, 202)
        except Exception as exc:  # noqa: BLE001
            print(f"  {endpoint} → 失败 {exc}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
