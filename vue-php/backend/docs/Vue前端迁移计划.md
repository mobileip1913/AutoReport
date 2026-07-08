# Vue 前端迁移计划（PHP 后端）

> 目标：前端改为 **Vue 3 SPA**，后端继续使用 **`php-backend/`（Slim 4 + JSON API）**，出报/取数逻辑不动。  
> 状态：规划稿（未开工）

---

## 1. 结论

| 问题 | 答案 |
|------|------|
| Vue + PHP 可行吗？ | **可行**，且比「Vue + 继续维护 Twig」更干净 |
| 最大难点在哪？ | **补齐页面级 GET 接口**（现在大量数据靠 Twig 注入 `window.*`） |
| 后端要重写吗？ | **不用**。`ReportEngine` / `FieldAggregator` 等保持 PHP |
| 推荐路线 | **分阶段 SPA（路线 B）**，不要长期维持 Twig + Vue 混跑 |

---

## 2. 现状盘点

### 2.1 页面（Twig → 需 Vue 化）

| 路由 | 模板 | 复杂度 | 说明 |
|------|------|--------|------|
| `/` | `dashboard.html.twig` | 低 | 静态 Hub，无复杂 JS |
| `/mappings` | `mappings.html.twig` | **高** | 数据源设置、日报字段表、辅助字段、刷单弹窗、取数弹窗 |
| `/daily` | `daily.html.twig` | **高** | 生成日报、字段编辑、拖拽排序、刷单导入、取数弹窗 |

导航栏：`base.html.twig`（账号切换 Cookie、店铺上下文）

### 2.2 现有前端 JS（需迁入 Vue 组件）

| 文件 | 行数级 | 职责 |
|------|--------|------|
| `mapping_modal.js` | ~1200 | 取数规则弹窗（最复杂） |
| `mappings_settings.js` | ~400+ | 数据源基准表、定时出报、刷单设置 |
| `daily_editor.js` | ~300+ | 日报行编辑、排序、保存 |
| `report_config.js` | 小 | 辅助 |

### 2.3 模板注入的全局变量（SPA 需改 API）

| 变量 | 页面 | 现状 API |
|------|------|----------|
| `current_account` / `account_menu` | 全局 | ❌ 无，仅 Twig |
| `current_store` / `accessible_stores` | mappings | ❌ 无 |
| `DATA_SOURCE_META` | mappings, daily | 部分：`GET /api/data-sources/{id}/schema` |
| `DS_SETTINGS` | mappings, daily | ✅ `GET .../settings` |
| `REUSE_FIELDS_BY_DS` | mappings, daily | 部分：`GET .../mapped-fields` |
| `excel_config` / 报表行列表 | mappings, daily | 部分：`GET .../report-lines` |
| `excel_rows` + `run` + `values` | daily | ❌ 无聚合接口 |
| `excel_templates` | mappings | ❌ 无 |

### 2.4 已有 PHP API（可直接复用）

写操作基本齐全：

- 映射 CRUD：`/api/mappings/*`、`/api/formula-lines/*`
- 报表字段：`/api/data-sources/{id}/report-fields/*`
- 报表值：`PATCH /api/report-runs/{id}/values/{id}`
- 数据源设置：`GET/PUT .../settings`
- 刷单：`.../review-orders/*`
- 配置导出：`.../config/export`
- 生成日报：`POST /api/generate`（页面目前用 `POST /daily/generate` 表单）

---

## 3. 目标架构

```
php-backend/
├── public/
│   ├── index.php          # Slim：/api/* + 文件下载 + SPA fallback
│   ├── static/            # 旧资源（迁移期保留）
│   └── app/               # Vue build 产物（index.html + assets/）
├── frontend/              # 新建：Vue 3 + Vite 工程
│   ├── src/
│   │   ├── api/           # axios 封装
│   │   ├── stores/        # Pinia
│   │   ├── views/         # 页面
│   │   ├── components/    # MappingModal、ReviewSettings…
│   │   └── router/
│   └── vite.config.ts     # base: '/app/' 或 '/'，与部署约定一致
└── src/                   # PHP 不变
```

**请求路径约定（推荐同源）：**

- `GET/POST /api/*` → `ApiController`
- `GET /daily/{id}/export` 等文件 → `PagesController`（保留）
- 其余 `GET /*` → `public/app/index.html`（Vue Router history）

**鉴权：** 继续 Cookie（`demo_account_id` / `demo_store_id`），前端 `axios` 设置 `withCredentials: true`。无需 JWT，除非未来要上生产多域。

---

## 4. 推荐技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 组件化、类型约束 mapping 结构 |
| 构建 | Vite | 快、与 PHP 解耦 |
| 路由 | Vue Router 4 | 3 个主页面 + query（`run_id`） |
| 状态 | Pinia | 当前店铺、schema、dsSettings |
| HTTP | axios | 统一错误处理 `detail` |
| UI | **Naive UI** 或 Element Plus | 表格/弹窗/表单；取数弹窗可逐步替换 |
| 样式 | 现有 **Tailwind** + `style.css` 变量 | 视觉延续，减少重写 |

不建议：CDN 版 Vue（路线 A）—— 你已选定 PHP 独立部署 + 长期迭代，直接上 Vite 工程更划算。

---

## 5. 分阶段实施计划

### 阶段 0：准备（0.5 天）

- [ ] 确认部署方式：开发时 Vite proxy → `8090`；生产 build 到 `public/app/`
- [ ] 在 `public/index.php` 或 Slim 中间件预留 SPA fallback
- [ ] 冻结 Twig 大改，新功能只走 Vue

### 阶段 1：补齐 PHP 读接口（2～3 天）⭐ 关键路径

新增 `SessionController` 或扩 `ApiController`：

| 接口 | 用途 |
|------|------|
| `GET /api/session` | 当前账号、可切换账号列表、当前店铺、可访问店铺与 data_source_id |
| `POST /api/session/account` | 替代 `POST /demo/switch-account` |
| `POST /api/session/store` | 替代 `POST /demo/switch-store` |
| `GET /api/mappings/bootstrap` | 聚合：stores、meta(schema)、ds_settings、reuse_fields、excel_config、logical_fields、pending_file_codes、excel_templates |
| `GET /api/daily/bootstrap?run_id=&data_source_id=` | 聚合：daily_sources、run、excel_rows、meta、ds_settings、schema、reuse_fields |
| `GET /api/meta/excel-templates` | 模板文件名列表（或并入 bootstrap） |

实现方式：从现有 `PagesController::mappings()` / `daily()` **抽取**组装逻辑到 `Services/PageBootstrap.php`，Twig 与 API 共用，避免双份逻辑。

表单类 POST 可逐步 JSON 化：

| 现有 | 新版 |
|------|------|
| `POST /daily/generate` | 已有 `POST /api/generate`，Vue 直接调用 |

### 阶段 2：Vue 脚手架（1 天）

- [ ] `frontend/` 初始化 Vite + Vue + Router + Pinia + Tailwind
- [ ] `api/client.ts`：baseURL、`withCredentials`、统一解析 `{ detail }`
- [ ] 布局组件：`AppLayout`（导航、账号切换）—— 对齐 `base.html.twig`
- [ ] 路由：`/`、`/mappings`、`/daily`

### 阶段 3：按页面迁移（核心 1.5～2 周）

**顺序：概览 → 报表配置 → 日报输出**（由易到难）

#### 3.1 概览 `/`（0.5 天）

- 静态 Hub UI，几乎无 API
- 验证：路由、布局、导航、账号切换

#### 3.2 报表配置 `/mappings`（4～5 天）

- [ ] `DsSettingsCard`：基准表、定时出报、导出 JSON
- [ ] `ReportFieldsTable` / `AuxFieldsTable`：规则摘要、操作按钮
- [ ] `ReviewSettingsModal`：刷单导入 + 物流费规则
- [ ] `MappingModal`：**最大块**，建议最后迁或分 composable（`useMappingParts`、`useCatalogTree`）
- 对照测试：保存设置、导出 JSON、打开取数弹窗、刷单设置

#### 3.3 日报输出 `/daily`（4～5 天）

- [ ] 顶栏：店铺、日期、`POST /api/generate`
- [ ] `DailyEditor`：拖拽排序、改标签、改报表值、状态标签
- [ ] 复用 `MappingModal`、`ReviewSettingsModal`
- [ ] 导出：`<a href="/daily/{id}/export">` 保持 URL 跳转（无需 axios blob 除非要进度条）

### 阶段 4：收尾（2～3 天）

- [ ] Twig 页面改为 302 → `/app/#/...` 或删除路由只留 API
- [ ] 删除/归档 `public/static/*.js` 旧脚本
- [ ] `php-backend/README.md` 增加前端构建说明
- [ ] 全链路回归：配置 → 生成日报 → 改值 → 导出 Excel/SKU → 对比 Python 数值（可选）

---

## 6. 工作量粗估

| 阶段 | 人天（1 人全职） |
|------|------------------|
| 0 准备 | 0.5 |
| 1 补 API | 2～3 |
| 2 脚手架 | 1 |
| 3 页面迁移 | 8～10 |
| 4 收尾回归 | 2～3 |
| **合计** | **约 2.5～3.5 周** |

若只做「报表配置 + 日报」两页、概览保持 Twig 重定向，可压到 **约 2 周**。

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| API 与 Twig 逻辑重复 | 抽 `PageBootstrap` 服务，单点组装 |
| `mapping_modal.js` 迁移工作量大 | 拆成多个 composable + 子组件；先保行为一致再优化 UI |
| Cookie 鉴权在 dev 跨端口失败 | Vite `proxy` 同源；或 dev 也走 `8090` 静态托管 build |
| PHP 内置服务器 SPA 路由 404 | `index.php` 对非 API 非文件请求返回 `app/index.html` |
| 回归出报数值 | 后端不动；用 `bin/compare_runs.php` 抽测 |

---

## 8. 与「PHP 项目复制出去」的关系

Vue 工程放在 `php-backend/frontend/`，build 进 `public/app/` 后，**整包 `php-backend/` 仍可独立拷贝部署**，只需：

```bash
cd frontend && npm ci && npm run build
cd .. && composer install && php bin/init.php
```

`.env` 配置 MySQL；`FILES_DIR` 指向 Excel 模板目录。

---

## 9. 不建议做的事

- 不要在迁移期同时大改取数引擎（`FieldAggregator` 等）
- 不要引入 Nuxt/SSR（无 SEO 需求，纯后台工具）
- 不要第一步就换 UI 库主题（先功能对齐再美化）
- 不要保留 Twig + Vue 双轨超过一个迭代周期

---

## 10. 下一步（开工清单）

1. 评审本计划，确认 **UI 库**（Naive UI / Element Plus）与 **部署 base 路径**（`/app/` vs `/`）
2. 实现 `GET /api/session` + `GET /api/mappings/bootstrap`（阶段 1 最小闭环）
3. 搭 `frontend/`，完成布局 + 概览页
4. 立项迁移 `MappingModal`（技术 spike：1 个简单 mapping 的加载/保存）

---

*文档版本：2026-07-08 · 后端基线：php-backend Slim 4 · 前端基线：Twig + 原生 JS*
