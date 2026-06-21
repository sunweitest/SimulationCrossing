# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 开发命令

虚拟环境位于项目外：`E:\pythonProject\InteractiveNovel\novel\`。以下命令均在项目根目录执行。

```bash
# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env                    # 编辑填入 API 密钥
E:/pythonProject/InteractiveNovel/novel/Scripts/python.exe -m alembic upgrade head
E:/pythonProject/InteractiveNovel/novel/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev
```

配置文件：`backend/app/core/config.py`（pydantic-settings，从 `.env` 加载）。

## 架构

### 后端层次

```
app/
├── main.py              # FastAPI 入口，CORS + 中间件 + 路由注册
├── api/                 # 路由层 (auth, game, admin)
├── services/            # 业务逻辑
│   ├── game_service.py  # 上下文构建/压缩/LLM调用/JSON解析
│   ├── context_compressor.py  # 文本摘要 + 角色 JSON 提取
│   ├── scene_image_matcher.py  # 场景图片向量匹配（embedding+余弦相似度）
│   └── llm/             # LLM Provider 抽象
│       ├── base.py      # 抽象基类
│       ├── deepseek_provider.py  # DeepSeek (OpenAI 兼容)
│       └── dashscope_provider.py # 阿里云百炼 (DashScope)
├── models/              # SQLAlchemy ORM
├── schemas/             # Pydantic 请求/响应
├── middleware/           # 速率限制
└── core/                # config, database, security
```

### 核心数据流（玩家行动）

```
game.py: POST /api/game/action
  → GameService.stream_story_text()               # 流式：注入角色上下文 → SSE 逐字推送 story_chunk
  → 并行: asyncio.gather(
      GameService.generate_scene_metadata(),       # 生成选项 + 游戏更新
      SceneImageMatcher.find_best_match(),         # 向量匹配场景图片
    )
  → 或 call_llm_api()（非流式）                   # 预过滤角色 + 启用 tool calling
    → DeepSeekProvider.generate()
      → _assemble_messages()                     # system prompt + 摘要前缀 + 历史 + 用户消息
      → tool call loop（最多 3 轮）              # LLM 主动 query_character()
  → GameService.parse_llm_response()             # 解析 JSON，先直接 json.loads 再正则兜底
  → 保存 SceneHistory / ChoiceHistory / 更新 GameSession
  → background_tasks: GameService.compress_and_store_context()  # 异步压缩 + 角色提取
```

### 上下文压缩（两阶段后台任务）

1. **文本摘要**（`deepseek-v4-pro`，低温 0.3）：将旧对话压缩为 `running_summary`（Text 列），注入到后续对话的 `【前情提要】` 前缀中。
2. **角色提取**（`deepseek-v4-flash`，低温 0.2）：从摘要中提取结构化人物数据，存入 `characters_state` JSON 列。每次增量合并——旧人物保留/更新，新人物追加。失败不影响摘要存储，下次重试。

触发条件：`total_turns > CONTEXT_COMPRESSION_THRESHOLD (6)`。压缩后只保留最近 `CONTEXT_RECENT_TURNS (3)` 轮完整对话。

### 场景图片匹配

启动时通过 DashScope `text-embedding-v4` 将 `frontend/public/images/scene/` 中的图片文件名（中文描述）转为 1024 维向量，缓存到 `backend/cache/scene_embeddings.json`。运行时将 LLM 生成的剧情文本嵌入后，通过余弦相似度（numpy 点积）匹配最佳场景图，作为全屏背景显示。

- **文件指纹**：SHA-256(filename+size 排序列表) 检测图片增删改，变化时自动重建缓存
- **匹配阈值**：`_MATCH_THRESHOLD = 0.26`，低于此值不返回图片（回退到世界背景图）
- **并行执行**：流式端点中 `asyncio.gather(metadata_generation, image_matching)` 并行，不增加延迟
- **图片服务**：通过 Vite `public/` 目录提供，URL 格式 `/images/scene/{filename}`

### 角色按需查询（替代全量注入）

**预过滤**：扫描用户输入，匹配 `characters_state` 中的角色名，只注入命中人物的 `【相关人物信息】`。

**Tool calling**：LLM 可通过 `query_character(name)` 主动查询未提及的人物（好感度/关系/状态），tool handler 从 `characters_state` JSON 中读取并返回。定义在 `CHARACTER_TOOLS`，tool loop 在 `DeepSeekProvider.generate()` 中处理。

### 双 Provider 模式

`LLM_PROVIDER` 配置选择 `deepseek` 或 `dashscope`。DeepSeek 走 OpenAI 兼容 API（含 tool calling），DashScope 走阿里云百炼无状态 Application API（不支持 tools）。`GameService.get_provider()` 惰性初始化单例。

### JSON 解析容错

`parse_llm_response()` 三级降级：

1. 直接 `json.loads` 全文（最优路径）
2. 正则提取 `{.*}` → sanitize 控制字符 → `json.loads`（兜底多余文字）
3. Smart fallback：用原始文本前 2000 字作为 scene_description，另调 `generate_choices()` 生成选项

### 速率限制

`RateLimitMiddleware`：未登录用户基于 IP+UA 指纹 + Redis 计数，每日 `DAILY_FREE_MESSAGES` 次；已登录用户额外 `DAILY_LOGGED_IN_EXTRA` 次。

### 数据库

PostgreSQL + asyncpg + SQLAlchemy 异步引擎。表结构由 Alembic 管理。关键表：

- `game_sessions`：会话状态 + `running_summary`(Text) + `characters_state`(JSON) + `summary_turn_count`
- `scene_history`：每轮 LLM 生成的场景 + 选项
- `choice_history`：每轮玩家选择

### 前端路由

- `/character-create` — 角色创建（首页）
- `/game/:id?` — 游戏主界面，可选 session id 参数
- `/my-games` — 我的游戏列表（需登录）
- `/admin` — 管理后台（无需登录，用 X-Admin-Key 验证）
- `/login`, `/register` — 认证页面

### 日志

业务日志级别在 `main.py` 中单独配置：`llm.deepseek` 和 `game_service` 设为 DEBUG。原始 DeepSeek 响应会保存到 `backend/logs/deepseek_raw_*.txt`。

## skill

代码根目录：skill.md

# 

### 日志

业务日志级别在 `main.py` 中单独配置：`llm.deepseek` 和 `game_service` 设为 DEBUG。原始 DeepSeek 响应会保存到 `backend/logs/deepseek_raw_*.txt`。

## 
