#!/bin/bash
set -e

# 等待 PostgreSQL 就绪
echo "=== 等待数据库就绪 ==="
python -c "
import asyncio
import asyncpg
import os
import time

async def wait():
    for i in range(30):
        try:
            conn = await asyncpg.connect(
                host=os.environ.get('DB_HOST', 'postgres'),
                port=os.environ.get('DB_PORT', '5432'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', 'mysecretpassword'),
                database=os.environ.get('DB_NAME', 'simulation_crossing'),
                timeout=5
            )
            await conn.close()
            print('  PostgreSQL 已就绪')
            return
        except Exception as e:
            print(f'  等待 PostgreSQL... ({i+1}/30)')
            time.sleep(2)
    raise RuntimeError('数据库连接超时')

asyncio.run(wait())
"

echo "=== 运行数据库迁移 ==="
python -m alembic upgrade head

echo "=== 启动服务 ==="
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
