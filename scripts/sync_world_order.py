#!/usr/bin/env python3
"""把数据库里的世界排序写回 content/worlds/*.json

排序是运营在后台「上移/下移」调的，只存在 `novel_configs.sort_order` 里。
导入脚本（import_content.py）已经**不再**用 JSON 的 sort_order 覆盖库里的值，
所以调完顺序要在后台点几下之后跑一次本脚本，让仓库里的 JSON 跟上，
否则别人 clone 下来自建库时顺序还是旧的。

用法（必须在 backend/ 之外、仓库根）：
    /opt/venv/bin/python scripts/sync_world_order.py          # 写回 JSON
    /opt/venv/bin/python scripts/sync_world_order.py --check  # 只比较，不写
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


async def _run(check: bool) -> int:
    os.chdir(REPO / "backend")
    sys.path.insert(0, str(REPO / "backend"))
    from sqlalchemy import select  # noqa: WPS433

    from app.core.database import AsyncSessionLocal  # noqa: WPS433
    from app.models.models import NovelConfig  # noqa: WPS433

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(NovelConfig).order_by(NovelConfig.sort_order, NovelConfig.id))).scalars().all()

    changed = 0
    for novel in rows:
        path = REPO / "content" / "worlds" / f"{novel.name}.json"
        if not path.exists():
            print(f"  · 没有 {novel.name}.json，跳过")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("sort_order") == novel.sort_order:
            continue
        print(f"  {'改用' if check else '写回'} {novel.name}: {data.get('sort_order')} → {novel.sort_order}")
        if not check:
            data["sort_order"] = novel.sort_order
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed += 1
    print(f"\n{'需要同步' if check else '已同步'} {changed} 个世界" + ("（--check 未写文件）" if check else ""))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比较，不写文件")
    args = ap.parse_args()
    asyncio.run(_run(args.check))


if __name__ == "__main__":
    main()
