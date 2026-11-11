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
        self._tags: List[List[str]] = []            # 与 entries 对齐的世界标签
        self._mask_cache: dict = {}
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

    def _image_files(self):
        """场景图文件列表：png 与 webp 都支持（webp 体积只有 png 的十分之一）"""
        files = list(self._image_dir.glob("*.png")) + list(self._image_dir.glob("*.webp"))
        return sorted(files, key=lambda p: p.name)

    def _compute_hash(self) -> str:
        """用文件名+大小的排序列表生成指纹，检测图片增删改"""
        info = sorted(
            (p.name, p.stat().st_size)
            for p in self._image_files()
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

        png_files = self._image_files()
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

    # ── 世界标签（公共图库 / 专属图库） ──────────────────

    def _load_tags(self) -> None:
        """读取 content/scene_images.json，给每张图打上可用世界。

        没有清单时所有图都算「通用」——行为与以前一致。
        """
        manifest = Path(__file__).resolve().parents[3] / "content" / "scene_images.json"
        tags_map: dict = {}
        if manifest.exists():
            try:
                tags_map = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                logger.warning("TAGS: 读取 %s 失败: %s", manifest, e)

        self._tags = []
        for e in self._entries:
            stem = Path(e["file"]).stem
            self._tags.append(tags_map.get(stem, ["通用"]))
        self._mask_cache = {}
        if tags_map:
            specific = sum(1 for t in self._tags if t != ["通用"])
            logger.info("TAGS: %d 张图，其中 %d 张为世界专属", len(self._tags), specific)

    def _allowed_mask(self, novel: str):
        """该世界可以用的图片：通用 + 本世界专属；没有标签时返回 None"""
        if not self._tags or not novel:
            return None
        if novel in self._mask_cache:
            return self._mask_cache[novel]
        mask = np.array(
            [("通用" in t) or (novel in t) for t in self._tags], dtype=bool
        )
        self._mask_cache[novel] = mask
        return mask

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
            self._load_tags()
            logger.info(
                "WARMUP: 缓存命中 %d 张图片 (%.1fs)", len(self._entries), time.time() - t0
            )
            return

        # 计算 embedding
        png_files = self._image_files()
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
        self._load_tags()
        self._ready = True
        self._save_cache()

        logger.info(
            "WARMUP: 完成 %d 张图片 embedding，耗时 %.1fs",
            len(self._entries), time.time() - t0,
        )

    # ── 运行时匹配 ────────────────────────────────────────

    async def find_best_match(self, story_text: str, novel: Optional[str] = None) -> Optional[str]:
        """传入剧情文本，返回最佳匹配的图片 URL，或 None

        流程：截取前 500 字 → embedding → 点积相似度 → 阈值判断
        novel 给出时先在该世界可用的图（通用 + 专属）里挑，挑不到再退回全库。
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

        # 世界优先：有专属图时先在本世界的候选里挑，避免「仙侠剧情配园林图」这类串味
        mask = self._allowed_mask(novel) if novel else None
        if mask is not None and mask.any():
            masked = np.where(mask, scores, -1.0)
            idx = int(np.argmax(masked))
            score = float(masked[idx])
            if score >= _MATCH_THRESHOLD:
                best_idx, best_score = idx, score

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
