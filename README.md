# AI互动小说游戏 - 完整项目说明

## 项目概述

一个基于 FastAPI + Vue 3 的 AI 互动小说游戏。玩家选一个世界（三国、水浒、西游、红楼、封神、金瓶梅、废土末世、武侠、仙侠、明/清、大唐长安、北宋汴京，共 13 个）和一个时间节点，以预设角色或自定义角色穿越进去；每一回合提交一个行动，模型续写剧情、给出三个选项并推进「使命」。

## 在线体验

官方实例：**https://wanchuanyue.com**（无需安装，注册即玩）

> 每日免费次数有限（未登录 5 次 / 登录 8 次），AI 生成有成本，请勿压测。
> 想自己部署？见 [部署](#部署)。

本项目以 AGPL-3.0 开源，你也可以完全自托管，官方实例不参与你的数据。

## 截图

<table>
<tr>
<td width="50%"><img src="docs/images/worlds.webp" alt="选择穿越世界：13 个世界，各有不同的时代与开场"><br>
<b>选世界 · 选时刻</b><br>13 个世界，从三国赤壁到废土末世，每个世界自带若干时间节点</td>
<td width="50%"><img src="docs/images/gameplay.webp" alt="剧情主界面：顶部使命条、正文、三个行动选项与自定义输入"><br>
<b>一回合一次抉择</b><br>顶部是使命与倒计时，正文由模型续写，底部三个行动选项 + 自由输入</td>
</tr>
<tr>
<td><img src="docs/images/rewind.webp" width="360" alt="回溯面板：列出每一回合的摘要与当时的选择"><br>
<b>回溯 · 每一步都留档</b><br>每回合的剧情与选择都落库，可回到任意一回合重来，积分与成就一起回退</td>
<td valign="top">

**为什么能回溯**：每回合的剧情、选项、积分与使命状态都写进 PostgreSQL，
回溯只删掉目标回合之后的记录并还原当时场景，不重新生成历史。

**为什么不会跑偏**：每个角色在每条时间线上都有一条「使命」，
分三个阶段、带回合期限；失败会进入下一幕，而不是从头再来。

</td>
</tr>
</table>

## 技术栈

### 后端
- **FastAPI** - 现代化的Python Web框架
- **SQLAlchemy** - 异步ORM
- **PostgreSQL** - 主数据库（异步驱动 asyncpg）
- **Redis** - 次数限制缓存
- **JWT** - 用户认证
- **DeepSeek** - 主模型服务；异常时自动切换阿里云百炼（同模型，选项用 qwen-plus）

### 前端
- **Vue 3** - 渐进式JavaScript框架
- **Vite** - 快速构建工具
- **Pinia** - 状态管理
- **Vue Router** - 路由管理
- **Axios** - HTTP客户端

## 核心功能

### ✅ 已实现功能

1. **用户系统**
   - 用户注册(支持邮箱/手机号)
   - 用户登录(JWT认证)
   - 未登录用户也可体验

2. **次数限制**
   - 未登录用户: 每日 5 次（按 IP）
   - 已登录用户: 每日 8 次（按账号）
   - Redis缓存实现,自动过期

3. **角色创建**
   - 13 个世界: 三国演义、水浒传、明代、清代、西游记、金瓶梅、废土末世、红楼梦、封神演义、武侠江湖、仙侠修真、大唐长安、北宋汴京
   - 多个时间节点选择
   - 预设经典角色(诸葛亮、赵云、曹操等)
   - 自定义角色创建

4. **游戏体验**
   - AI实时生成剧情
   - 流式响应展示
   - 打字机效果显示
   - 多选项行动建议
   - 自由输入行动
   - 积分和成就系统

5. **使命与回溯**
   - 每个角色在每条时间线上有专属「使命」：3 个阶段 + 回合期限
   - 使命失败会进入下一幕（由模型结合失败原因生成新目标），主角死亡则本局结束
   - 任意回合可回溯，积分与成就一起回退

6. **UI设计**
   - 简约风格
   - 响应式布局
   - 流畅动画效果
   - 友好交互体验

> 改代码先看 [`docs/代码地图.md`](docs/代码地图.md)：功能 → 前端文件 → 接口 → 后端服务 → 数据表 / 配置项，一张表定位。

## 项目结构

```
服务器/
├── backend/              # FastAPI后端
│   ├── app/
│   │   ├── api/         # API路由
│   │   ├── core/        # 核心配置
│   │   ├── middleware/  # 中间件
│   │   ├── models/      # 数据库模型
│   │   ├── schemas/     # Pydantic模型
│   │   ├── services/    # 业务逻辑
│   │   └── main.py      # 应用入口
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/            # Vue.js前端
│   ├── src/
│   │   ├── api/        # API封装
│   │   ├── assets/     # 静态资源
│   │   ├── router/     # 路由
│   │   ├── stores/     # 状态管理
│   │   ├── views/      # 页面组件
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
└── qwen_python.py       # 原始Streamlit demo
```

## 快速开始

### 1. 启动Redis

```bash
# 使用Docker
docker run -d -p 6379:6379 redis:alpine

# 或使用本地Redis
redis-server
```

### 2. 启动后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件,填入必要的API密钥

# 运行服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问: http://localhost:8000/docs 查看API文档

### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

前端启动后访问: http://localhost:5173

## 环境配置

### 后端环境变量(.env)

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://novel_user:your-password@localhost:5432/simulation_crossing

# JWT密钥(生产环境必须修改!)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 模型服务（必填）
DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 备用模型（可选）：主链路超时/5xx 时自动切换，指向阿里云百炼兼容端点
LLM_FAILOVER_ENABLED=true
LLM_FAILOVER_API_KEY=your-dashscope-key
LLM_FAILOVER_BASE_URL=https://llm-t2prhzae03osgg8c.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
LLM_FAILOVER_MODEL=deepseek-v4.1-flash

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:8080

# 次数限制
DAILY_FREE_MESSAGES=26
DAILY_LOGGED_IN_EXTRA=10
```

## API接口文档

### 认证接口

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录

### 游戏接口

- `POST /api/game/session` - 创建游戏会话
- `POST /api/game/action` - 执行游戏行动
- `GET /api/game/session/{id}` - 获取游戏会话
- `GET /api/game/session/{id}/state` - 获取游戏状态

详细接口文档访问: http://localhost:8000/docs

## 数据库模型

### User (用户表)
- id, email, phone, hashed_password, is_active, created_at

### GameSession (游戏会话表)
- id, user_id, session_id, character_name, character_gender, character_age
- character_rank, character_background, novel, timeline, character_type
- points, achievements, current_scene, created_at, updated_at

### SceneHistory (场景历史表)
- id, game_session_id, scene_description, choices, points_awarded, achievement

### ChoiceHistory (选择历史表)
- id, game_session_id, choice, points, created_at

## 前后端交互流程

1. **用户注册/登录**
   - 前端发送注册/登录请求
   - 后端验证并返回JWT token
   - 前端存储token到localStorage

2. **创建游戏会话**
   - 前端发送角色信息
   - 后端创建GameSession记录
   - 返回初始场景

3. **执行游戏行动**
   - 前端发送用户行动
   - 后端调用主模型（DeepSeek，异常时切阿里云百炼）生成剧情
   - 解析JSON响应
   - 更新游戏状态
   - 保存历史记录
   - 返回新场景

4. **次数限制检查**
   - 中间件拦截游戏行动请求
   - 检查Redis中的计数
   - 超限返回429错误
   - 前端提示用户登录

## 部署

### 后端部署

```bash
# 使用Gunicorn + Uvicorn
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 前端部署

```bash
# 构建生产版本
npm run build

# 使用Nginx部署dist目录
# 配置反向代理到后端API
```

### 部署方式说明

线上环境为**原生部署**：systemd 托管 uvicorn + nginx 反代 + 本机 PostgreSQL / Redis。
发布脚本在服务器本地维护，不纳入本仓库。

> ⚠️ 仓库里的 `docker-compose.yml` 为**历史遗留、未维护**，与实际运行方式不一致（端口冲突、env_file 指向模板等），请勿用于生产部署，详见该文件头部注释。

## 未来扩展功能

根据`产品描述.md`中的需求,可以加:

### 盈利功能
- 会员订阅系统(基础/高级/VIP)
- 点数/代币系统
- 内容付费(高级角色、特殊剧情)
- 自定义剧本市场
- 广告收入

### 社区互动
- 首页底部「联系作者反馈」按钮（QQ: 1306344250）
- 首页底部「Git仓库欢迎贡献代码」按钮

### 社交功能
- 剧情分享
- 排行榜系统
- 用户打赏

### 企业服务
- 教育机构定制
- 团队建设定制

## 常见问题

### 1. Redis连接失败
确保Redis服务已启动,检查端口是否正确

### 2. 模型调用失败 / 剧情一直转圈
先看 `journalctl -u novel-backend` 里有没有 `LLM_FAILOVER`、`NEXT_ACT_FALLBACK`；
检查 `.env` 的 `DEEPSEEK_API_KEY` 与备用 `LLM_FAILOVER_*` 是否配置、余额是否充足。

### 3. 前端无法访问后端
检查CORS配置,确认前端URL在CORS_ORIGINS中

### 4. 数据库初始化失败
确认 PostgreSQL 已启动、`DATABASE_URL` 指向正确库；表结构由 Alembic 管理：

```bash
cd backend && alembic upgrade head
```

## 相关链接

- GitHub: [https://github.com/sunweitest/SimulationCrossing](https://github.com/sunweitest/SimulationCrossing)
- 作者反馈: QQ 1306344250

## 开发团队

项目由 AI 辅助开发完成

## 加一个世界（内容与代码分离）

世界内容以 `content/worlds/*.json` 为唯一来源，不写在迁移里：

```bash
# 导入/更新（按名字 upsert，可重复执行）
python scripts/import_content.py import --file content/worlds/红楼梦.json
python scripts/import_content.py import --dir content/worlds
# 看各世界数据量
python scripts/import_content.py check
```

新增世界还需要：封面图 + `covers/*.webp` 缩略图、`CharacterCreateView.vue` 的 `worldImageMap`、
`MyGamesView.vue` 的封面映射、`LadderView.vue` 的 `COVERS`（详见 `docs/代码地图.md` 第 9 节）。

现有 13 个世界：三国演义、水浒传、明代、清代、西游记、金瓶梅、废土末世、红楼梦、封神演义、
武侠江湖、仙侠修真、大唐长安·天宝末年、北宋汴京之变；其中 47 个是「小人物」（差役、丫鬟、小妖、船工…）。

## 许可证

GNU AGPL-3.0（见 [LICENSE](LICENSE)）

