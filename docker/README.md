# AutoReport MySQL（Docker）

在 **192.168.128.212** 上执行：

```bash
cd /path/to/AutoReport/docker
docker compose --env-file .env up -d
docker compose ps
```

默认账号（可在 `docker/.env` 修改）：

| 变量 | 默认值 |
|------|--------|
| MYSQL_ROOT_PASSWORD | AutoReport@2026 |
| MYSQL_USER | autoreport |
| MYSQL_PASSWORD | AutoReport@2026 |
| MYSQL_DATABASE | autoreport |
| 端口 | 3306 |

应用侧在项目根目录复制 `.env.example` 为 `.env`，设置：

```
DATABASE_URL=mysql+pymysql://autoreport:AutoReport%402026@192.168.128.212:3306/autoreport?charset=utf8mb4
```

## 若 3306 已有旧 MySQL 且密码未知

```bash
docker stop autoreport-mysql 2>/dev/null || true
docker rm autoreport-mysql 2>/dev/null || true
# 如需清空数据：docker volume rm docker_autoreport_mysql_data
docker compose --env-file .env up -d
```

## 初始化数据

在开发机（能访问 212:3306）：

```bash
python scripts/import_meichong.py --force
python scripts/setup_meichong.py 2026-06-22
```

## 生产注意

- 修改强密码，勿提交 `.env`
- 212 防火墙仅放行内网 3306
- 定期备份 volume `autoreport_mysql_data`
- ETL 更新：将新 Excel 放入 `files/` 后重跑 `import_meichong.py --force`
