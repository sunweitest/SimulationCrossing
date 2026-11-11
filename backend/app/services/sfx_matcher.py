"""音效智能匹配器

思路与场景图完全一致：把每条音效的中文描述做 text-embedding，运行时用剧情文本
求余弦相似度，挑最像的一条播放。区别只在文件是 mp3、语料来自 content/sfx.json。

音效是公共库（`frontend/public/audio/sfx/`），各世界按 tags 取用：
- tags 含「通用」= 古装/不分题材都可用；
- 现代题材（都市霸总 / 都市修真 / 日常生活）只吃打了本世界标签的音效，
  否则会在写字楼里放更鼓声。

Usage:
    await init_sfx_matcher(audio_dir, cache_path, api_key)
    hit = await get_sfx_matcher().find_best_match(story_text, novel="金瓶梅")
    # → {"name": ..., "url": "/audio/sfx/xxx.mp3", "score": 0.41, "duration": 2.3} or None
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger("sfx_matcher")

_DASHSCOPE_EMBED_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DASHSCOPE_EMBED_MODEL = "text-embedding-v4"
_DASHSCOPE_EMBED_DIM = 1024
_BATCH_SIZE = 10
# 音效宁可不放，也不要放错。按「拆句取最大相似度」实测校准：
# 正例 0.56~0.83（刀剑/空调/雨/街道/杯盏/电话/竹林/拔刀），
# 反例 0.33~0.50（账册/训话/对视/递茶/合同/纪要），取 0.55 作分界——
# 0.48 时「往董事长桌上一拍」会匹到玻璃杯（0.504），宁可不响也不放错。
_MATCH_THRESHOLD = 0.55
MODERN_WORLDS = {"都市修真", "日常生活", "都市霸总"}


class SfxMatcher:
    def __init__(self, audio_dir: Path, cache_path: Path, manifest_path: Path, api_key: str):
        self._audio_dir = audio_dir
        self._cache_path = cache_path
        self._manifest_path = manifest_path
        self._api_key = api_key
        self._client: Optional[OpenAI] = None
        self._entries: list[dict] = []
        self._matrix: Optional[np.ndarray] = None
        self._tags: list[list[str]] = []
        self._mask_cache: dict = {}
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key, base_url=_DASHSCOPE_EMBED_BASE, timeout=30.0)
        return self._client

    def _audio_files(self) -> list[Path]:
        return sorted(self._audio_dir.glob("*.mp3"), key=lambda p: p.name)

    def _manifest(self) -> dict:
        if not self._manifest_path.exists():
            return {}
        try:
            return json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("MANIFEST: 读取失败 %s", exc)
            return {}

    def _compute_hash(self) -> str:
        info = sorted((p.name, p.stat().st_size) for p in self._audio_files())
        raw = json.dumps(info, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_cache(self) -> bool:
        if not self._cache_path.exists():
            return False
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return False
        if data.get("file_hash") != self._compute_hash():
            logger.info("CACHE: 音效指纹变化，重新计算")
            return False
        files = self._audio_files()
        if len(files) != len(data.get("embeddings", [])):
            return False
        manifest = self._manifest()
        self._entries = []
        self._tags = []
        for p, emb in zip(files, data["embeddings"]):
            meta = manifest.get(p.stem, {})
            self._entries.append(
                {
                    "name": p.stem,
                    "file": p.name,
                    "url": f"/audio/sfx/{p.name}",
                    "duration": meta.get("duration"),
                    "vector": np.array(emb, dtype=np.float32),
                }
            )
            self._tags.append(meta.get("tags") or ["通用"])
        self._build_matrix()
        self._ready = True
        logger.info("CACHE: 音效缓存命中 %d 条", len(self._entries))
        return True

    def _save_cache(self) -> None:
        data = {
            "file_hash": self._compute_hash(),
            "model": _DASHSCOPE_EMBED_MODEL,
            "embeddings": [e["vector"].tolist() for e in self._entries],
            "names": [e["name"] for e in self._entries],
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")

    async def _batch_embed(self, texts: list[str]) -> list[np.ndarray]:
        client = self._get_client()
        out: list[np.ndarray] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]

            def _call():
                resp = client.embeddings.create(
                    model=_DASHSCOPE_EMBED_MODEL,
                    input=batch,
                    dimensions=_DASHSCOPE_EMBED_DIM,
                    encoding_format="float",
                )
                ordered = sorted(resp.data, key=lambda d: d.index)
                return [np.array(d.embedding, dtype=np.float32) for d in ordered]

            out.extend(await asyncio.to_thread(_call))
            if i + _BATCH_SIZE < len(texts):
                await asyncio.sleep(0.15)
        return out

    def _build_matrix(self) -> None:
        if not self._entries:
            self._matrix = None
            return
        m = np.stack([e["vector"] for e in self._entries])
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = m / norms

    def _allowed_mask(self, novel: str):
        if not self._tags or not novel:
            return None
        if novel in self._mask_cache:
            return self._mask_cache[novel]
        if novel in MODERN_WORLDS:
            mask = np.array([novel in t for t in self._tags], dtype=bool)
        else:
            mask = np.array([("通用" in t) or (novel in t) for t in self._tags], dtype=bool)
        self._mask_cache[novel] = mask
        return mask

    async def warmup(self) -> None:
        t0 = time.time()
        if not self._audio_dir.exists():
            logger.warning("WARMUP: 音效目录不存在 %s，匹配器不启用", self._audio_dir)
            return
        if self._load_cache():
            logger.info("WARMUP: 音效就绪 %d 条 (%.1fs)", len(self._entries), time.time() - t0)
            return

        files = self._audio_files()
        if not files:
            logger.warning("WARMUP: %s 里没有 mp3", self._audio_dir)
            return

        manifest = self._manifest()
        texts = [manifest.get(p.stem, {}).get("desc") or p.stem for p in files]
        logger.info("WARMUP: 为 %d 条音效计算 embedding", len(texts))
        vectors = await self._batch_embed(texts)

        self._entries = []
        self._tags = []
        for p, v in zip(files, vectors):
            meta = manifest.get(p.stem, {})
            self._entries.append(
                {
                    "name": p.stem,
                    "file": p.name,
                    "url": f"/audio/sfx/{p.name}",
                    "duration": meta.get("duration"),
                    "vector": v,
                }
            )
            self._tags.append(meta.get("tags") or ["通用"])
        self._build_matrix()
        self._ready = True
        self._save_cache()
        logger.info("WARMUP: 音效就绪 %d 条，耗时 %.1fs", len(self._entries), time.time() - t0)

    @staticmethod
    def _queries(story_text: str, action: Optional[str]) -> list[str]:
        """把剧情拆成几个「事件片段」分别去比，取最像的那个。

        整段 500 字一起 embed 时事件会被稀释（「刀劈空了」整段里只占一句），
        拆句后单句命中率明显更高；玩家这一回合的动作本身也是强信号。
        """
        parts: list[str] = []
        if action:
            parts.append(action.strip()[:60])
        text = (story_text or "").strip()
        chunks = re.split(r"[。！？；\n]+", text)
        picked = [c.strip() for c in chunks if 6 <= len(c.strip()) <= 60][:8]
        parts.extend(picked)
        if not parts and text:
            parts.append(text[:80])
        # 去重保序
        seen, out = set(), []
        for p in parts:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out[:9]

    async def find_best_match(
        self, story_text: str, novel: Optional[str] = None, action: Optional[str] = None
    ) -> Optional[dict]:
        if not self._ready or self._matrix is None:
            return None
        queries = self._queries(story_text, action)
        if not queries:
            return None

        client = self._get_client()

        def _embed_queries():
            resp = client.embeddings.create(
                model=_DASHSCOPE_EMBED_MODEL,
                input=queries,
                dimensions=_DASHSCOPE_EMBED_DIM,
                encoding_format="float",
            )
            ordered = sorted(resp.data, key=lambda d: d.index)
            vecs = np.stack([np.array(d.embedding, dtype=np.float32) for d in ordered])
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return vecs / norms

        try:
            query_vecs = await asyncio.to_thread(_embed_queries)
        except Exception as exc:  # noqa: BLE001
            logger.error("MATCH: 查询 embedding 失败: %s", exc)
            return None

        # (句子数 × 音效数) 的相似度矩阵，取全局最大
        scores = query_vecs @ self._matrix.T
        mask = self._allowed_mask(novel) if novel else None
        if mask is not None:
            if not mask.any():
                return None
            scores = np.where(mask, scores, -1.0)

        flat = int(np.argmax(scores))
        q_idx, e_idx = np.unravel_index(flat, scores.shape)
        score = float(scores[q_idx, e_idx])
        entry = self._entries[int(e_idx)]
        logger.info(
            "SFX_MATCH: score=%.3f name=%s query=%.40s",
            score, entry["name"], queries[int(q_idx)],
        )
        if score < _MATCH_THRESHOLD:
            return None
        return {
            "name": entry["name"],
            "url": entry["url"],
            "score": round(score, 3),
            "duration": entry.get("duration"),
        }


_matcher: Optional[SfxMatcher] = None


def get_sfx_matcher() -> Optional[SfxMatcher]:
    return _matcher


async def init_sfx_matcher(audio_dir: Path, cache_path: Path, manifest_path: Path, api_key: str) -> SfxMatcher:
    global _matcher
    _matcher = SfxMatcher(audio_dir, cache_path, manifest_path, api_key)
    await _matcher.warmup()
    return _matcher
