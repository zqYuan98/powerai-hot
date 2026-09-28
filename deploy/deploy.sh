#!/usr/bin/env bash
# 构建 → 迁移 → 同步信源 → 启动 → 健康检查。可重复执行。
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "缺少 deploy/.env，请先 cp .env.example .env 并填写"; exit 1; }
dc() { docker compose --env-file .env -f compose.yml "$@"; }

echo "==> 构建镜像"
dc build

echo "==> 启动数据库"
dc up -d --wait db

echo "==> 数据库迁移"
dc run --rm --no-deps api alembic upgrade head

echo "==> 同步信源注册表与默认订阅"
dc run --rm --no-deps api python -m app.cli seed

echo "==> 启动服务"
dc up -d --wait --remove-orphans

echo "==> 健康检查"
dc exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
dc ps
echo "完成。查看日志：docker compose -f deploy/compose.yml logs -f worker"
