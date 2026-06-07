#!/bin/bash
set -e

echo "=== 拉取最新代码 ==="
git pull

echo "=== 从本地 .env 生成 .env.production.local ==="
if [ -f "backend/.env" ]; then
  grep -E "^(DASHSCOPE_API_KEY|SHUIHU_APP_ID|SANGUO_APP_ID|MINGDAI_APP_ID|QINGDAI_APP_ID|SECRET_KEY)=" backend/.env > .env.production.local 2>/dev/null
  echo "  API Key 已同步到 .env.production.local"
fi

echo "=== 构建并重启 ==="
docker compose down
docker compose up --build -d

echo "=== 等待服务就绪 ==="
sleep 5
docker compose ps

echo ""
echo "部署完成！访问 http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_IP')"
