#!/usr/bin/env bash
# 在 192.168.128.212 上启动 AutoReport MySQL（需已安装 Docker）
set -euo pipefail
cd "$(dirname "$0")/../docker"
docker compose --env-file .env up -d
docker compose ps
echo ""
echo "MySQL 已启动。连接串示例："
echo "  mysql+pymysql://autoreport:AutoReport%402026@192.168.128.212:3306/autoreport?charset=utf8mb4"
