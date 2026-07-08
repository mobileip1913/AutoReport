# Vue 前端迁移计划（vue-php 工程）

本文件自 `php-backend/docs/Vue前端迁移计划.md` 同步，**实施路径以本目录为准**：

- 前端代码：`vue-php/frontend/`
- 后端代码：`vue-php/backend/`（不再改 `php-backend/` 的 Twig 与静态 JS）
- 开发端口：Vue **5173**，PHP **8091**

完整计划内容见仓库内 [php-backend/docs/Vue前端迁移计划.md](../../php-backend/docs/Vue前端迁移计划.md)，后续更新请优先修改本目录下文档副本。

## 当前状态

1. **阶段 0 完成**：独立 `vue-php/` 工程、Vite 代理、三页路由骨架  
2. **下一步**：在 `backend` 增加 `GET /api/session`、`GET /api/mappings/bootstrap`，再迁 MappingModal
