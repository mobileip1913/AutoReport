# AutoReport Demo

跨境电商自动报表 Demo：财务在 Web 上配置**报表行**（取数 + 公式 + 分组 + 格式），系统从 **MySQL** 读取业务数据并自动生成日经营报表。

## 快速启动

```bash
cd AutoReport
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 复制并编辑数据库连接
copy .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

浏览器打开 http://localhost:8081（局域网可用本机 IP 访问）。

## Demo 流程

1. **报表配置** — 调整各指标取数规则与公式（`/mappings`）
2. **报表配置**（`/mappings`）— 取数规则、公式行、分组与格式合一配置，保存即生效
3. **日报输出** — 选店铺与日期，从 `fact_*` 事实表聚合出报

> Web 端**不再上传 Excel**。Demo/生产数据由 MySQL 预先准备好。旧「报表模板」页已重定向至报表配置。

## 数据库

在 `.env` 中配置：

```env
DATABASE_URL=mysql+pymysql://user:pass%40host:3306/autoreport?charset=utf8mb4
```

密码含特殊字符需 URL 编码（如 `@` → `%40`）。

| 表域 | 说明 |
|------|------|
| `catalog_*` | 文件 / Sheet / 列头 目录 |
| `fact_*` | 业务行数据（出报取数） |
| `field_mapping_*` | 字段映射配置 |
| `report_*` | 模板与报表结果 |

本地开发若无 MySQL，可临时用 SQLite（不推荐用于美宠大数据量 Demo）。

## 可选：离线灌库（仅开发）

```bash
python scripts/import_meichong.py --force
python scripts/test_mysql_connection.py
```

生产环境由运维/RPA 维护 MySQL，无需此步骤。
