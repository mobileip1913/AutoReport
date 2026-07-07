# AutoReport Demo

跨境电商自动报表 Demo：财务配置字段映射与报表模板，系统解析 Excel 并自动生成日经营报表。

## 快速启动

```bash
cd d:\Code\AutoReport
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

或直接双击 `run.bat`，浏览器打开 http://localhost:8000

## Demo 流程

1. **字段映射** — 逻辑字段 ↔ Excel Sheet/列头
2. **报表模板** — 测试生成 → 确认 → 发布
3. **数据导入** — 上传 Excel，列头不匹配写映射日志
4. **报表输出** — 查看日经营报表

## 数据库

- 默认 SQLite（`data/autoreport.db`），零配置
- 生产可改 `.env` 中 `DATABASE_URL` 为 MySQL
- 大规模分析可考虑 ClickHouse
