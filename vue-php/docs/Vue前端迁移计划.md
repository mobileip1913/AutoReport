# Vue 前端迁移计划（vue-php 工程）

> **实施路径以本目录为准**；Twig 过渡版见 `php-backend/`（8090）。

| 项 | 路径 |
|----|------|
| Vue 前端 | `vue-php/frontend/` → :5173 |
| PHP API | `vue-php/backend/` → :8091 |
| 参考 UI（Twig） | `php-backend/templates/` + `static/` → :8090 |
| **执行清单** | **[Vue迁移Checklist.md](./Vue迁移Checklist.md)** ← 日常勾选用这个 |

---

## 1. 结论

| 问题 | 答案 |
|------|------|
| PHP 前端要改成 Vue 吗？ | **是**，目标套件为 `vue-php/` |
| 改完了吗？ | **没有**，目前仅 ~5% 脚手架 |
| 现在能用哪个？ | **8090 Twig** 已对齐 Python；5173 Vue 仅探活 |
| 后端要重写吗？ | 不用；镜像 `php-backend` 业务 + 补 Bootstrap JSON API |

---

## 2. 架构

```
vue-php/
├── frontend/          # Vue 3 SPA（目标默认 UI）
│   └── vite.config.ts # dev proxy → 8091
└── backend/           # Slim 4 JSON API（从 php-backend 独立演进）
    └── public/app/    # 生产 build 产物
```

- 开发：`5173`（Vite）+ `8091`（PHP）
- 生产：build 进 `public/app/`，PHP SPA fallback
- 鉴权：Cookie（`demo_account_id` / `demo_store_id`），axios `withCredentials: true`

完整分阶段说明见仓库 [php-backend/docs/Vue前端迁移计划.md](../../php-backend/docs/Vue前端迁移计划.md)（架构细节）；**进度与勾选以 [Vue迁移Checklist.md](./Vue迁移Checklist.md) 为准**。

---

## 3. 推荐实施顺序

1. **镜像 backend**（`php-backend` → `vue-php/backend`）+ API 冒烟 8091  
2. **Bootstrap API**（`session` / `mappings/bootstrap` / `daily/bootstrap`）+ `PageBootstrap`  
3. **Vue 基建**（Pinia、样式、Toast/Modal）  
4. **页面**：概览 → mappings → daily  
5. **切换**：8090 重定向或下线 Twig，文档标注 Vue 为默认  

---

*2026-07-09 · Checklist 驱动执行*
