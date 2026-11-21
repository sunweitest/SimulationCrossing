#!/usr/bin/env python3
"""生成 SEO 静态页 / sitemap / robots / IndexNow 校验文件

前端是 SPA，`/w/<slug>.html` 这些页面**不依赖 JS**：世界介绍、时间线、角色列表
在 HTML 里就是明文，爬虫（含 AI 抓取器）不用执行脚本也能读到内容。

产物（全部落到 frontend/public，跟着 npm run build 进 dist）：
    w/<slug>.html          每个世界一页
    sitemap.xml            静态路由 + 16 个世界页
    robots.txt             放行公开页、屏蔽 /api /admin /game 等私有路径
    <indexnow-key>.txt     IndexNow 校验文件（首次生成后固定不变）

用法（仓库根）：
    python3 scripts/gen_seo_pages.py
    python3 scripts/gen_seo_pages.py --dry-run
"""

from __future__ import annotations

import argparse
import html
import json
import secrets
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORLDS_DIR = REPO / "content" / "worlds"
PUBLIC = REPO / "frontend" / "public"
SITE = "https://wanchuanyue.com"

# 与 frontend/src/utils/worldArt.js 的 WORLD_ART 保持一致
SLUGS = {
    "三国演义": "sanguo", "水浒传": "shuihu", "明代": "mingdai", "清代": "qingdai",
    "西游记": "xiyou", "金瓶梅": "jinpingmei", "废土末世": "wasteland",
    "红楼梦": "hongloumeng", "封神演义": "fengshen", "武侠江湖": "wuxia",
    "仙侠修真": "xianxia", "大唐长安·天宝末年": "datang", "北宋汴京之变": "bianjing",
    "都市修真": "urban", "日常生活": "daily", "都市霸总": "bazong",
}

STATIC_PAGES = [
    ("", "1.0", "daily"),
    ("character-create", "0.9", "weekly"),
    ("ladder", "0.8", "daily"),
    ("pricing", "0.7", "monthly"),
    ("privacy", "0.3", "yearly"),
    ("terms", "0.3", "yearly"),
    ("refund", "0.3", "yearly"),
]

DISALLOW = ["/api/", "/admin", "/game/", "/my-games", "/login", "/register"]

CRAWLERS = [
    "*", "Googlebot", "bingbot", "Baiduspider", "YisouSpider", "Sogou web spider",
    "GPTBot", "ClaudeBot", "PerplexityBot", "Bytespider", "Applebot",
]

CSS = """
:root{--ink:#f4efe4;--dim:#b9ae99;--gold:#e8c76a;--bg:#0b0b12;--line:rgba(232,199,106,.22)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:var(--gold);text-decoration:none}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
.hero{position:relative;min-height:46vh;display:flex;align-items:flex-end;
background-size:cover;background-position:center 30%}
.hero:after{content:"";position:absolute;inset:0;
background:linear-gradient(180deg,rgba(6,6,12,.35),rgba(6,6,12,.94))}
.hero .wrap{position:relative;z-index:2;padding-bottom:28px}
h1{font-size:clamp(28px,5vw,46px);margin:0 0 6px;letter-spacing:.06em}
.cap{color:var(--gold);letter-spacing:.18em;font-size:13px;margin:0 0 14px}
.desc{color:var(--dim);max-width:44em;margin:0 0 20px}
.cta{display:inline-block;padding:11px 22px;border:1px solid var(--gold);border-radius:999px;
color:var(--gold);font-size:15px}
section{padding:38px 0;border-top:1px solid var(--line)}
h2{font-size:19px;letter-spacing:.14em;color:var(--gold);margin:0 0 18px;font-weight:500}
.tls{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.tl{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:rgba(255,255,255,.02)}
.tl b{display:block;margin-bottom:6px}
.tl span{color:var(--dim);font-size:14px}
.chars{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:16px}
.ch{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:rgba(255,255,255,.02)}
.ch img{width:100%;aspect-ratio:400/516;object-fit:cover;display:block;background:#161620}
.ch .meta{padding:9px 11px}
.ch b{display:block;font-size:15px}
.ch span{color:var(--dim);font-size:12px}
.ch p{color:var(--dim);font-size:12px;margin:6px 0 0;line-height:1.6;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.more{display:flex;flex-wrap:wrap;gap:10px}
.more a{border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:13px;color:var(--dim)}
footer{color:#7c7466;font-size:13px;padding:26px 0 40px}
"""


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def world_page(novel: str, data: dict) -> str:
    slug = SLUGS.get(novel, "sanguo")
    caption = data.get("tagline") or data.get("caption") or ""
    desc = (data.get("description") or "").strip()
    timelines = data.get("timelines") or []
    chars = [c for c in (data.get("characters") or []) if c.get("role") != "minor"][:12]
    url = f"{SITE}/w/{slug}.html"
    title = f"{novel} · AI 穿越模拟"

    tl_html = "".join(
        f'<div class="tl"><b>{esc(t.get("name"))}</b><span>{esc((t.get("description") or "")[:96])}</span></div>'
        for t in timelines
    )
    ch_html = ""
    for c in chars:
        img = c.get("image") or ""
        if img and img.startswith("/"):
            img = SITE + img
        ch_html += (
            '<div class="ch">'
            + (f'<img src="{esc(img)}" alt="{esc(c.get("name"))}" loading="lazy">' if img else "")
            + '<div class="meta">'
            + f'<b>{esc(c.get("name"))}</b>'
            + f'<span>{esc(c.get("rank"))} · {esc(c.get("age"))}岁</span>'
            + f'<p>{esc((c.get("background") or "")[:70])}</p>'
            + "</div></div>"
        )

    others = "".join(
        f'<a href="/w/{s}.html">{esc(n)}</a>' for n, s in SLUGS.items() if n != novel
    )
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": novel,
        "description": desc[:180],
        "url": url,
        "inLanguage": "zh-CN",
        "isPartOf": {"@type": "WebSite", "name": "AI 穿越模拟", "url": SITE},
        "genre": "互动小说",
    }

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc((desc or caption)[:150])}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc((desc or caption)[:150])}">
<meta property="og:image" content="{SITE}/images/hero/{slug}.webp">
<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
<div class="hero" style="background-image:url('/images/hero/{slug}.webp')">
  <div class="wrap">
    <p class="cap">{esc(caption)}</p>
    <h1>{esc(novel)}</h1>
    <p class="desc">{esc(desc[:220])}</p>
    <a class="cta" href="/character-create">选一个角色，开始穿越 →</a>
  </div>
</div>

<section><div class="wrap">
  <h2>可穿越的时间点</h2>
  <div class="tls">{tl_html}</div>
</div></section>

<section><div class="wrap">
  <h2>可以扮演的人物</h2>
  <div class="chars">{ch_html}</div>
</div></section>

<section><div class="wrap">
  <h2>换个世界</h2>
  <div class="more">{others}</div>
</div></section>

<footer><div class="wrap">
  © 2026 wanchuanyue.com · <a href="{SITE}/">AI 穿越模拟</a> · 剧情由 AI 生成，仅供娱乐。
</div></footer>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    worlds = []
    for f in sorted(WORLDS_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        novel = data.get("novel") or f.stem
        worlds.append((novel, data))
    worlds.sort(key=lambda x: x[1].get("sort_order", 999))

    key_path = REPO / "content" / "indexnow_key.txt"
    if key_path.exists():
        index_key = key_path.read_text().strip()
    else:
        index_key = secrets.token_hex(16)
        print(f"生成 IndexNow key: {index_key}")

    if args.dry_run:
        for novel, data in worlds:
            print(f"[{SLUGS.get(novel, '?')}] {novel}  角色 {len(data.get('characters') or [])}")
        print(f"共 {len(worlds)} 个世界页")
        return

    out_dir = PUBLIC / "w"
    out_dir.mkdir(parents=True, exist_ok=True)
    for novel, data in worlds:
        slug = SLUGS.get(novel, "sanguo")
        (out_dir / f"{slug}.html").write_text(world_page(novel, data), encoding="utf-8")

    today = time.strftime("%Y-%m-%d")
    urls = [f"{SITE}/{p}" if p else SITE + "/" for p, _, _ in STATIC_PAGES]
    entries = [
        f"  <url><loc>{esc(u)}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for u, pr, cf in [(f"{SITE}/{p}" if p else SITE + "/", pr, cf) for p, pr, cf in STATIC_PAGES]
    ]
    for novel, _ in worlds:
        entries.append(
            f"  <url><loc>{SITE}/w/{SLUGS.get(novel, 'sanguo')}.html</loc>"
            f"<lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )
        urls.append(f"{SITE}/w/{SLUGS.get(novel, 'sanguo')}.html")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    (PUBLIC / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    robots = []
    for ua in CRAWLERS:
        robots.append(f"User-agent: {ua}")
        robots.append("Allow: /")
        robots.extend(f"Disallow: {p}" for p in DISALLOW)
        robots.append("")
    robots.append(f"Sitemap: {SITE}/sitemap.xml")
    (PUBLIC / "robots.txt").write_text("\n".join(robots) + "\n", encoding="utf-8")

    # 只在内容变了才写：key 是长期固定的，反复覆盖会踩到文件属主（部署时 chown 成 www-data，
    # 手工用 root/ubuntu 跑就会 Permission denied），也容易让 git 多出无意义的改动。
    if not key_path.exists() or key_path.read_text(encoding="utf-8").strip() != index_key:
        key_path.write_text(index_key + "\n", encoding="utf-8")
    key_file = PUBLIC / f"{index_key}.txt"
    if not key_file.exists() or key_file.read_text(encoding="utf-8").strip() != index_key:
        key_file.write_text(index_key + "\n", encoding="utf-8")

    print(f"世界页 {len(worlds)} 个 → {out_dir}")
    print(f"sitemap.xml {len(entries)} 条 / robots.txt / IndexNow {index_key[:8]}…")


if __name__ == "__main__":
    main()
