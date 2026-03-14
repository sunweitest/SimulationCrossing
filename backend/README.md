# FastAPI后端 - AI互动小说游戏

## 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

## 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置:

```bash
cp .env.example .env
```

必须配置:
- `SECRET_KEY`: JWT密钥（生产环境必须修改）
- `DASHSCOPE_API_KEY`: 阿里云DashScope API密钥
- `SANGUO_APP_ID`, `SHUIHU_APP_ID`, `MINGDAI_APP_ID`, `QINGDAI_APP_ID`: 各个故事世界的应用ID

## 启动Redis（用于次数限制）

```bash
# 使用Docker启动Redis
docker run -d -p 6379:6379 redis:alpine

# 或使用系统安装的Redis
redis-server
```

## 运行应用

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问:
- API文档: http://localhost:8000/docs
- 根路径: http://localhost:8000

## 项目结构

```
backend/
├── app/
│   ├── api/           # API路由
│   │   ├── auth.py    # 认证相关接口
│   │   ├── game.py    # 游戏相关接口
│   │   └── deps.py    # 依赖项
│   ├── core/          # 核心配置
│   │   ├── config.py  # 配置管理
│   │   ├── database.py # 数据库连接
│   │   └── security.py # 安全工具(JWT/密码)
│   ├── middleware/    # 中间件
│   │   └── rate_limit.py # 次数限制中间件
│   ├── models/        # 数据库模型
│   │   └── models.py
│   ├── schemas/       # Pydantic模型
│   │   └── schemas.py
│   ├── services/      # 业务逻辑
│   │   └── game_service.py # 游戏服务(LLM调用)
│   └── main.py        # 应用入口
├── requirements.txt   # 依赖列表
└── .env.example       # 环境变量示例
```

## API接口

### 认证接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录

### 游戏接口
- `POST /api/game/session` - 创建游戏会话
- `POST /api/game/action` - 执行游戏行动
- `GET /api/game/session/{id}` - 获取游戏会话
- `GET /api/game/session/{id}/state` - 获取游戏状态

## 次数限制规则

- 未登录用户: 每日26条消息（基于IP+User-Agent指纹）
- 已登录用户: 每日36条消息（26+10）
- 超限后返回429状态码，提示登录
