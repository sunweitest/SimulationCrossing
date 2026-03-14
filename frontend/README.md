# Vue.js 前端 - AI互动小说游戏

## 安装依赖

```bash
cd frontend
npm install
```

## 开发模式运行

```bash
npm run dev
```

访问: http://localhost:5173

## 构建生产版本

```bash
npm run build
```

构建后的文件在 `dist/` 目录

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API接口封装
│   │   └── index.js      # axios配置和API方法
│   ├── assets/           # 静态资源
│   │   └── styles/
│   │       └── main.css  # 全局样式
│   ├── components/       # 可复用组件
│   ├── router/           # 路由配置
│   │   └── index.js
│   ├── stores/           # Pinia状态管理
│   │   ├── auth.js       # 认证状态
│   │   └── game.js       # 游戏状态
│   ├── views/            # 页面组件
│   │   ├── LoginView.vue         # 登录页
│   │   ├── RegisterView.vue      # 注册页
│   │   ├── CharacterCreateView.vue # 角色创建页
│   │   └── GameView.vue          # 游戏主界面
│   ├── App.vue           # 根组件
│   └── main.js           # 入口文件
├── index.html            # HTML模板
├── package.json
└── vite.config.js        # Vite配置
```

## 功能特性

### 用户认证
- ✅ 用户注册（支持邮箱/手机号）
- ✅ 用户登录
- ✅ JWT令牌管理
- ✅ 未登录也可游戏

### 角色创建
- ✅ 选择小说/历史背景
- ✅ 选择时间节点
- ✅ 预设角色选择
- ✅ 自定义角色创建
- ✅ 实时角色预览

### 游戏体验
- ✅ AI生成剧情
- ✅ 打字机效果显示剧情
- ✅ 多选项行动建议
- ✅ 自定义行动输入
- ✅ 积分和成就系统
- ✅ 次数限制提示

### UI设计
- ✅ 简约古典风格
- ✅ 响应式布局
- ✅ 流畅动画效果
- ✅ 友好错误提示

## 配置说明

### API代理
在 `vite.config.js` 中配置了API代理,所有 `/api` 开头的请求会代理到后端服务器(默认 http://localhost:8000)

### 状态持久化
- Token和用户信息存储在 localStorage
- 页面刷新后状态保持

## 开发提示

1. 确保后端服务已启动
2. 修改代码后会自动热更新
3. 查看浏览器控制台获取详细错误信息
