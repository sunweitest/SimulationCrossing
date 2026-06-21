"""场景图片智能匹配器

使用 DashScope text-embedding-v4 将图片中文文件名转换为向量。
启动时预计算并缓存到磁盘，运行时通过余弦相似度匹配剧情文本。
支持 5-1000 张图片，纯 numpy 内存匹配，无需外部向量数据库。

Usage:
    # 启动时
    await init_matcher(image_dir, cache_path, api_key)

    # 运行时
    matcher = get_matcher()
    url = await matcher.find_best_match(story_text)  # → "/images/scene/xxx.png" or None
"""

import json
import hashlib
import logging
import asyncio
import time
from pathlib import Path
from typing import Optional, List

import numpy as np
from openai import OpenAI

logger = logging.getLogger("scene_image_matcher")

# DashScope embedding 兼容端点（OpenAI SDK）
_DASHSCOPE_EMBED_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DASHSCOPE_EMBED_MODEL = "text-embedding-v4"
_DASHSCOPE_EMBED_DIM = 1024
_BATCH_SIZE = 10  # embedding API 每批最多 10 条
_MATCH_THRESHOLD = 0.26  # 余弦相似度阈值，低于此值不返回图片


class SceneImageMatcher:
    """场景图片匹配器（单例）"""

    def __init__(self, image_dir: Path, cache_path: Path, api_key: str):
        self._image_dir = image_dir
        self._cache_path = cache_path
        self._api_key = api_key
        self._client: Optional[OpenAI] = None
        self._entries: List[dict] = []  # [{"file": "xxx.png", "url": "/images/scene/xxx.png", "vector": np.array}, ...]
        self._matrix: Optional[np.ndarray] = None  # (N, 1024) L2-normalized
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=_DASHSCOPE_EMBED_BASE,
                timeout=30.0,
            )
        return self._client

    # ── 文件指纹 ──────────────────────────────────────────

    def _compute_hash(self) -> str:
        """用文件名+大小的排序列表生成指纹，检测图片增删改"""
        info = sorted(
            (p.name, p.stat().st_size)
            for p in self._image_dir.glob("*.png")
        )
        raw = json.dumps(info, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── 缓存读写 ──────────────────────────────────────────

    def _load_cache(self) -> bool:
        """从磁盘加载缓存。返回 True 表示加载成功"""
        if not self._cache_path.exists():
            logger.info("CACHE: 缓存文件不存在")
            return False

        try:
            data = json.loads(self._cache_path.read_text("utf-8"))
        except (json.JSONDecodeError, KeyError):
            logger.warning("CACHE: 缓存文件损坏")
            return False

        if data.get("file_hash") != self._compute_hash():
            logger.info("CACHE: 文件指纹已变化，需要重新计算")
            return False

        png_files = sorted(self._image_dir.glob("*.png"))
        if len(png_files) != len(data.get("embeddings", [])):
            logger.info("CACHE: 图片数量变化")
            return False

        self._entries = []
        for p, emb_list in zip(png_files, data["embeddings"]):
            vec = np.array(emb_list, dtype=np.float32)
            self._entries.append({
                "file": p.name,
                "url": f"/images/scene/{p.name}",
                "vector": vec,
            })
        self._build_matrix()
        self._ready = True
        logger.info("CACHE: 从缓存加载 %d 个向量", len(self._entries))
        return True

    def _save_cache(self) -> None:
        """将当前向量写入磁盘缓存"""
        data = {
            "file_hash": self._compute_hash(),
            "model": _DASHSCOPE_EMBED_MODEL,
            "embeddings": [e["vector"].tolist() for e in self._entries],
            "filenames": [e["file"] for e in self._entries],
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(data, ensure_ascii=False), "utf-8"
        )
        logger.info("CACHE: 已保存 %d 个向量到 %s", len(self._entries), self._cache_path)

    # ── Embedding API ─────────────────────────────────────

    async def _batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """批量调用 embedding API，每批最多 _BATCH_SIZE 条"""
        client = self._get_client()
        all_vectors = []

        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i:i + _BATCH_SIZE]
            logger.info(
                "EMBED: batch %d/%d (%d items)",
                i // _BATCH_SIZE + 1,
                (len(texts) + _BATCH_SIZE - 1) // _BATCH_SIZE,
                len(batch),
            )

            def _call():
                resp = client.embeddings.create(
                    model=_DASHSCOPE_EMBED_MODEL,
                    input=batch,
                    dimensions=_DASHSCOPE_EMBED_DIM,
                    encoding_format="float",
                )
                # 按 index 排序确保与输入顺序一致
                sorted_data = sorted(resp.data, key=lambda d: d.index)
                return [np.array(d.embedding, dtype=np.float32) for d in sorted_data]

            vectors = await asyncio.to_thread(_call)
            all_vectors.extend(vectors)

            # 批次间留间隔，避免触发限流
            if i + _BATCH_SIZE < len(texts):
                await asyncio.sleep(0.15)

        return all_vectors

    # ── 矩阵构建 ──────────────────────────────────────────

    def _build_matrix(self) -> None:
        """将 entries 中的向量堆叠为 L2-归一化矩阵，供高效点积匹配"""
        if not self._entries:
            self._matrix = None
            return
        m = np.stack([e["vector"] for e in self._entries])  # (N, 1024)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = m / norms

    # ── 启动预热 ──────────────────────────────────────────

    async def warmup(self) -> None:
        """启动时调用：加载缓存或重新计算 embedding"""
        t0 = time.time()

        # 先检查目录是否存在
        if not self._image_dir.exists() or not self._image_dir.is_dir():
            logger.warning(
                "WARMUP: 图片目录不存在 %s，匹配器不启用", self._image_dir
            )
            return

        # 尝试从缓存加载
        if self._load_cache():
            logger.info(
                "WARMUP: 缓存命中 %d 张图片 (%.1fs)", len(self._entries), time.time() - t0
            )
            return

        # 计算 embedding
        png_files = sorted(self._image_dir.glob("*.png"))
        if not png_files:
            logger.warning("WARMUP: %s 中没有 .png 图片", self._image_dir)
            return

        display_names = [p.stem for p in png_files]  # 中文名，去掉 .png
        logger.info("WARMUP: 开始为 %d 张图片计算 embedding...", len(display_names))

        vectors = await self._batch_embed(display_names)

        self._entries = [
            {
                "file": p.name,
                "url": f"/images/scene/{p.name}",
                "vector": v,
            }
            for p, v in zip(png_files, vectors)
        ]
        self._build_matrix()
        self._ready = True
        self._save_cache()

        logger.info(
            "WARMUP: 完成 %d 张图片 embedding，耗时 %.1fs",
            len(self._entries), time.time() - t0,
        )

    # ── 运行时匹配 ────────────────────────────────────────

    async def find_best_match(self, story_text: str) -> Optional[str]:
        """传入剧情文本，返回最佳匹配的图片 URL，或 None

        流程：截取前 500 字 → embedding → 点积相似度 → 阈值判断
        """
        if not self._ready:
            return None

        text = story_text.strip() if story_text else ""
        if not text:
            return None

        # 截取前 500 字用于匹配（足够捕捉场景主题）
        query_text = text[:500]

        client = self._get_client()

        def _embed_query():
            resp = client.embeddings.create(
                model=_DASHSCOPE_EMBED_MODEL,
                input=query_text,
                dimensions=_DASHSCOPE_EMBED_DIM,
                encoding_format="float",
            )
            vec = np.array(resp.data[0].embedding, dtype=np.float32)
            # L2 归一化
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec

        try:
            query_vec = await asyncio.to_thread(_embed_query)
        except Exception as e:
            logger.error("MATCH: 查询 embedding 失败: %s", e)
            return None

        if query_vec is None:
            return None

        # 点积 = 余弦相似度（矩阵和查询向量都已归一化）
        scores = self._matrix @ query_vec
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        logger.info(
            "MATCH: best_idx=%d score=%.3f file=%s query=%.40s",
            best_idx, best_score, self._entries[best_idx]["file"], query_text,
        )

        if best_score < _MATCH_THRESHOLD:
            logger.info(
                "MATCH: 分数 %.3f 低于阈值 %.2f，不返回图片",
                best_score, _MATCH_THRESHOLD,
            )
            return None

        return self._entries[best_idx]["url"]


# ── 模块级单例 ────────────────────────────────────────────

_matcher: Optional[SceneImageMatcher] = None


def get_matcher() -> Optional[SceneImageMatcher]:
    """获取全局匹配器实例（可能为 None，如果启动时初始化失败）"""
    return _matcher


async def init_matcher(
    image_dir: Path,
    cache_path: Path,
    api_key: str,
) -> SceneImageMatcher:
    """初始化全局匹配器并预热"""
    global _matcher
    _matcher = SceneImageMatcher(
        image_dir=image_dir,
        cache_path=cache_path,
        api_key=api_key,
    )
    await _matcher.warmup()
    return _matcher
