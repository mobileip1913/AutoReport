# AutoReport Vue + PHP

独立于仓库内 **Twig 版 `php-backend/`** 与 **Python `app/`** 的一套前后端分离工程。

| 组件 | 目录 | 默认端口 |
|------|------|----------|
| Vue 3 前端 | `frontend/` | **5173**（开发） |
| PHP API + 静态托管 | `backend/` | **8091** |

原有服务不受影响：

- Python FastAPI：`8081`（`app/`）
- Twig PHP：`8090`（`php-backend/`）

---

## 目录结构

```
vue-php/
├── frontend/          # Vue 3 + Vite + TypeScript
│   ├── src/
│   └── vite.config.ts # 开发代理 /api → 8091；build → backend/public/app/
├── backend/           # Slim 4 + PDO（自 php-backend 复制，独立演进）
│   ├── public/
│   ├── src/
│   └── bin/
├── files/             # Excel 日报模板（可选，见 FILES_DIR）
├── docs/              # 迁移与实现文档
└── README.md
```

整包 **`vue-php/`** 可复制到任意目录单独部署；与 AutoReport 主仓库解耦。

---

## 快速开始

### 1. 后端

```powershell
cd vue-php\backend
copy .env.example .env
# 编辑 .env 填写 MySQL（可与主项目共用库）

composer install
php bin\init.php
php -S 0.0.0.0:8091 -t public
```

### 2. 前端（另开终端）

```powershell
cd vue-php\frontend
npm install
npm run dev
```

浏览器打开：**http://127.0.0.1:5173/**

### 3. 生产构建（单端口）

```powershell
cd vue-php\frontend
npm run build
# 产物在 backend/public/app/

cd ..\backend
php -S 0.0.0.0:8091 -t public
# 访问 http://127.0.0.1:8091/app/ （需后续在 index.php 配置 SPA fallback）
```

开发期推荐 **5173 + 8091** 双进程；生产再将 Vue build 进 `public/app/` 并由 PHP 统一对外。

---

## 与主仓库的关系

| 项 | 说明 |
|----|------|
| 数据库 | 可共用 `autoreport` MySQL；表结构由 `bin/init.php` 维护 |
| 业务逻辑 | 初期从 `php-backend` 复制；之后在 `vue-php/backend` 独立改 |
| 前端 | **全新 Vue**，不修改 `php-backend/templates` 与 `public/static/*.js` |
| Python | 完全不依赖；ETL 仍用主仓库 `scripts/` 灌数 |

---

## 迁移进度

- [x] 独立目录与端口
- [x] Vue 路由骨架（概览 / 报表配置 / 日报输出）
- [x] API 客户端 + 开发代理
- [ ] `GET /api/session`、`/api/mappings/bootstrap` 等读接口
- [ ] 报表配置页组件（MappingModal、DsSettings…）
- [ ] 日报编辑器

详见 [docs/Vue前端迁移计划.md](docs/Vue前端迁移计划.md)。

---

## 一键启动（Windows）

```powershell
.\scripts\dev.ps1
```

（同时启动 PHP 8091 与 Vite 5173；见 `scripts/dev.ps1`。）
