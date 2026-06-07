# AI互动小说游戏 - 完整项目说明

## 项目概述

这是一个基于FastAPI + Vue.js开发的AI互动小说游戏,玩家可以穿越到中国古典小说(三国演义、水浒传)或历史时期(明代、清代),扮演经典角色或自定义角色,通过AI生成剧情进行互动冒险。

## 技术栈

### 后端
- **FastAPI** - 现代化的Python Web框架
- **SQLAlchemy** - 异步ORM
- **SQLite** - 轻量级数据库
- **Redis** - 次数限制缓存
- **JWT** - 用户认证
- **DashScope** - 阿里云AI大模型API

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
   - 未登录用户: 每日26次消息(基于IP+User-Agent指纹)
   - 已登录用户: 每日36次消息(26+10)
   - Redis缓存实现,自动过期

3. **角色创建**
   - 4个世界背景: 三国演义、水浒传、明代、清代
   - 多个时间节点选择
   - 预设经典角色(诸葛亮、赵云、曹操、宋江等)
   - 自定义角色创建

4. **游戏体验**
   - AI实时生成剧情
   - 流式响应展示
   - 打字机效果显示
   - 多选项行动建议
   - 自由输入行动
   - 积分和成就系统

5. **UI设计**
   - 简约古典风格
   - 响应式布局
   - 流畅动画效果
   - 友好交互体验

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
DATABASE_URL=sqlite+aiosqlite:///./game.db

# JWT密钥(生产环境必须修改!)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# DashScope API (必填!)
DASHSCOPE_API_KEY=your-api-key
SHUIHU_APP_ID=your-app-id
SANGUO_APP_ID=your-app-id
MINGDAI_APP_ID=your-app-id
QINGDAI_APP_ID=your-app-id

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
   - 后端调用DashScope API生成剧情
   - 解析JSON响应
   - 更新游戏状态
   - 保存历史记录
   - 返回新场景

4. **次数限制检查**
   - 中间件拦截游戏行动请求
   - 检查Redis中的计数
   - 超限返回429错误
   - 前端提示用户登录

## 部署建议

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

### 使用Docker Compose

可以创建docker-compose.yml一键部署完整服务(后端+前端+Redis+Nginx)

## 未来扩展功能

根据`产品描述.md`中的需求,可以加:

### 盈利功能
- 会员订阅系统(基础/高级/VIP)
- 点数/代币系统
- 内容付费(高级角色、特殊剧情)
- 自定义剧本市场
- 广告收入

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

### 2. DashScope API调用失败
检查.env中的API密钥是否正确,账户余额是否充足

### 3. 前端无法访问后端
检查CORS配置,确认前端URL在CORS_ORIGINS中

### 4. 数据库初始化失败
删除game.db文件,重新启动后端自动创建

## 开发团队

项目由Claude Code辅助开发完成

## 许可证

MIT License

