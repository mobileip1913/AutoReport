# AutoReport Vue + PHP（独立可拷贝套件）

整包 **`vue-php/`** 可复制到任意目录单独部署，不依赖仓库内 `app/`、`php-backend/`。

| 组件 | 目录 | 说明 |
|------|------|------|
| Vue 3 前端 | `frontend/` | Naive UI + Pinia，生产 build → `backend/public/app/` |
| PHP API | `backend/` | Slim 4，端口 **8091** |
| Excel 模板 | `files/` | 可选，`.env` 中 `FILES_DIR` |

**技术选型（已定）**

- UI：**Naive UI**
- 生产路径：**`/app/`**（访问 `http://host:8091/app/`）
- 鉴权：Cookie + axios `withCredentials`

---

## 独立部署（推荐）

```powershell
# 1. 拷贝整个 vue-php 目录到目标机器
# 2. 安装 + 构建
cd vue-php
.\scripts\install.ps1

# 3. 编辑 backend\.env 填写 MySQL

# 4. 启动（单端口，含 Vue）
.\scripts\serve.ps1
# → http://127.0.0.1:8091/app/
```

`install.ps1` 会：`composer install` → `php bin/init.php` → `npm install` → `npm run build`。

---

## 开发（双进程）

```powershell
.\scripts\dev.ps1
```

- Vue：**http://127.0.0.1:5173/app/**（Vite 代理 `/api` → 8091）
- API：**http://127.0.0.1:8091**

---

## 目录结构

```
vue-php/
├── frontend/          # Vue 源码（Vite base=/app/）
├── backend/
│   ├── public/
│   │   ├── index.php  # API + SPA fallback
│   │   └── app/       # npm run build 产物（勿手改）
│   ├── src/
│   └── bin/
│       ├── init.php
│       └── api_smoke_test.py
├── files/
├── scripts/
│   ├── install.ps1    # 一键安装
│   ├── serve.ps1      # 生产单端口
│   └── dev.ps1        # 开发双进程
└── docs/
    └── Vue迁移Checklist.md
```

---

## API 冒烟

```powershell
cd backend
php bin/init.php
# 另开终端先 serve.ps1 或 dev.ps1
python bin\api_smoke_test.py
```

---

## 与主仓库关系

| 工程 | 用途 |
|------|------|
| `app/` (8081) | Python 参考实现 |
| `php-backend/` (8090) | Twig 过渡版（对照用） |
| **`vue-php/` (8091)** | **Vue 默认前端（本套件）** |

数据库可与主项目共用 `autoreport` MySQL；表由 `backend/bin/init.php` 维护。

---

## 迁移进度

见 [docs/Vue迁移Checklist.md](docs/Vue迁移Checklist.md)。

- [x] 独立目录、`/app/` 构建、SPA fallback
- [x] Backend 镜像 + Bootstrap API（session / mappings / daily）
- [x] Naive UI + Pinia + 三页初版（bootstrap 驱动）
- [ ] MappingModal / DailyEditor 完整迁移
- [ ] 全链路 browser-act 验收
