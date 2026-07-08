# AutoReport PHP 后端（vue-php 工程内）

> 本目录属于 **`vue-php/backend`**，与仓库内 Twig 版 `php-backend/` **独立并行**。  
> 默认端口 **8091**；Twig 版仍为 **8090**。前端为 `vue-php/frontend/`（Vue 3）。

与仓库根目录的 Python (FastAPI) 版功能对等的 PHP 实现，共用同一个 MySQL 数据库时可与主项目共存，进程与代码互不影响。

## 技术选型对照

| 能力 | Python 版 | PHP 版 |
| --- | --- | --- |
| Web 框架 | FastAPI | Slim 4 |
| 模板 | Jinja2 | Twig（语法几乎一致） |
| 数据库 | SQLAlchemy | PDO（MySQL / SQLite） |
| Excel | openpyxl | PhpSpreadsheet |
| 定时任务 | APScheduler（进程内） | `bin/scheduler.php` + 系统计划任务 |
| 配置 | pydantic-settings + .env | vlucas/phpdotenv |

## 目录结构

```
php-backend/
├── bin/
│   ├── init.php           # 初始化：建表 + 种子数据（对等 on_startup）
│   └── scheduler.php      # 定时出报（由计划任务每分钟调用）
├── public/
│   ├── index.php          # 入口 + 全部路由
│   └── static/            # 前端静态资源（与 Python 版同源复制）
├── src/
│   ├── Config.php         # 环境配置（.env）
│   ├── Database.php       # PDO 封装（MySQL/SQLite）
│   ├── Migrate.php        # 建表与增量迁移
│   ├── Bootstrap.php      # 启动序列（迁移+种子+规则同步）
│   ├── Views.php          # Twig 环境（含 cst 时区过滤器）
│   ├── HttpError.php      # 对等 FastAPI HTTPException
│   ├── Controllers/
│   │   ├── PagesController.php   # 页面路由（对等 routers/pages.py）
│   │   └── ApiController.php     # API 路由（对等 routers/api.py）
│   └── Services/          # 业务服务（与 app/services/ 一一对应）
├── templates/             # Twig 模板（与 app/templates/ 一一对应）
├── docs/                  # PHP 后端专项文档
│   ├── 生成日报流程与实现.md
│   └── PHP报表取数与SQL实现.md
├── composer.json
└── .env
```

## 快速开始

```bash
cd php-backend
composer install

# 1. 配置 .env（MySQL 连接；不配 MYSQL_PASSWORD 时回落 SQLite）

# 2. 初始化（建表 + 种子数据，幂等可重复执行）
php bin/init.php

# 3. 启动开发服务器（端口避开 Twig 版 8090 与 Python 8081）
php -S 0.0.0.0:8091 -t public
```

访问 http://127.0.0.1:8091 。前端开发请用 `vue-php/frontend` 的 Vite（5173）。

### 定时出报

PHP 没有进程内后台调度，改用系统计划任务每分钟执行：

```
# Windows 任务计划程序 / Linux cron
* * * * *  php e:\code\AutoReport\php-backend\bin\scheduler.php
```

脚本按各店铺 `daily_generate_at`（Asia/Shanghai）到点生成昨日正式日报，`data/scheduler_state.json` 保证同日只出一次。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/生成日报流程与实现.md](docs/生成日报流程与实现.md) | 点击「生成日报」后的完整链路与代码索引 |
| [docs/PHP报表取数与SQL实现.md](docs/PHP报表取数与SQL实现.md) | 模板/映射/Catalog/SQL 与内存聚合分工 |

仓库根目录 `docs/` 另有全栈 PRD、技术架构等通用文档。

## 迁移 Checklist

### 基础层
- [x] Composer 依赖（Slim 4 / Twig / PhpSpreadsheet / phpdotenv）
- [x] Config（.env 加载，MySQL/SQLite 回落）
- [x] Database（PDO 封装：查询、插入、更新、表结构探测、JSON 编解码）
- [x] Migrate（全部 14 张表建表 + 增量加列，与 SQLAlchemy 模型对齐）
- [x] HttpError（`{"detail": "..."}` 错误结构对齐 FastAPI）

### 业务服务（app/services/ → src/Services/）
- [x] MappingUtils（行编码/标签/行类型判断/展示过滤）
- [x] Formula（`{field:code}` 提取、安全四则运算求值、数值格式化）
- [x] Timezone（UTC → Asia/Shanghai `cst` 过滤器）
- [x] DsSettings（日期主表、每日生成时间、刷单单号配置）
- [x] CatalogResolver / SchemaService（目录/表结构查询）
- [x] FactProvider（MySQL 事实表读取 + 列别名映射）
- [x] MappingRepo（映射 + parts 水合、API 序列化）
- [x] FieldAggregator（日报上下文、行过滤、样品/刷单排除、去重聚合、多来源组合）
- [x] ReportEngine（出报、补值、旧模板兼容）
- [x] Seed / MeichongRules（美宠数据源、逻辑字段、默认映射种子）
- [x] ReportLineSync（模板行同步、公式行转取数、line_code 回填、旧数据迁移）
- [x] StoreClone / DemoAccounts（店铺克隆、Demo 账号种子）
- [x] AccountContext（Cookie 账号/店铺切换、数据源权限校验）
- [x] DailyReport（日报行构建、Excel 导出含模板样式复制）
- [x] SkuExport（SKU 明细导出）
- [x] ReviewImport（刷单模板生成 / 导入解析）

### 路由与页面
- [x] 页面路由 15 条（概览/报表配置/日报输出/导出/账号店铺切换/旧路径重定向）
- [x] API 路由 20 条（映射 CRUD、公式行、报表字段增序改、值覆写、数据源设置、刷单模板/导入、生成）
- [x] Twig 模板 5 个（base/dashboard/mappings/daily/mapping_modal 局部）
- [x] 静态资源复制（daily_editor.js / mapping_modal.js / mappings_settings.js / style.css / tailwind.css）

### CLI 与运维
- [x] bin/init.php（初始化，幂等）
- [x] bin/scheduler.php（定时出报 + 状态文件防重）
- [ ] 生产部署：nginx + php-fpm 指向 public/（按需）

### 验证
- [x] 页面冒烟：/ /mappings /daily 均 200；/logs → /mappings、/reports → /daily 重定向
- [x] 生成日报并与 Python 版数值对比（run 数值逐项一致，可用 `php bin/compare_runs.php <日期> <runA> <runB>` 复验）
- [x] 日报 Excel / SKU 明细导出（200，xlsx 内容正常返回）
- [x] 刷单模板下载（页面路由与 API 路由均通过）
- [x] 账号切换与 Cookie 生效（切换后导航栏账号变更）
- [x] bin/scheduler.php 到点出报冒烟通过
- [ ] 刷单导入端到端（需真实刷单文件，界面操作验证）

## 与 Python 版共存注意事项

- 两个后端共用同一 MySQL 库；表结构由双方 `CREATE TABLE IF NOT EXISTS` + 增量加列维持一致。
- Python 版跑在 8000 端口，PHP 版建议 8090，前端静态资源各自独立复制，互不影响。
- `report_runs.created_at` 等时间统一存 UTC，展示层各自转 Asia/Shanghai。
- 未迁移项：`/api/import` 上传导入在 Python 版已废弃（410），PHP 版保持同样行为；模板页 `/templates*` 与 Python 版一致统一重定向到 /mappings。
