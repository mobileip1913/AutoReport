# Vue 前端迁移 Checklist

> **目标**：PHP 可操作前端从 **Twig + 原生 JS**（`php-backend/` :8090）迁到 **Vue 3 SPA**（`vue-php/frontend/` :5173），后端 API 走 **`vue-php/backend/`** :8091。  
> **原则**：Twig 版作参考实现，新功能只加 Vue；`php-backend` 仅作短期对照，不长期双轨维护。

---

## 当前状态（2026-07-09）

| 工程 | 路径 | 端口 | 前端 | 完成度 |
|------|------|------|------|--------|
| Python 参考 | `app/` | 8081 | Jinja + JS | 100%（主线） |
| Twig PHP（过渡） | `php-backend/` | 8090 | Twig + JS | **功能已对齐 Python**（daily hub / 样品 / 运费 / 出报） |
| **Vue + PHP（目标）** | `vue-php/` | 5173 + 8091 | **Vue 3 + Naive UI** | **~75%**（三页 Hub + 核心弹窗；MappingModal 简化版） |

**结论**：Vue 主流程已可用（`http://127.0.0.1:8091/app/`）；8090 Twig 仍作完整对照。剩余：MappingModal 全量 parity、Aux/Review/Schedule 弹窗、DailyEditor 拖拽。

---

## 阶段总览

```
[0] 决策冻结 ──► [1] 后端镜像 + Bootstrap API ──► [2] Vue 基建 ──► [3] 页面迁移 ──► [4] 收尾切换
     ✅ 已定              ✅ 完成                    ✅ 完成           🟡 ~85%            🟡 部分
```

预估剩余：**3～5 天**（MappingModal 全量 + 辅助弹窗 + 8090 切换）。

---

## 阶段 0：决策与冻结 ✅

- [x] 独立套件目录 `vue-php/`（不破坏 `app/`、`php-backend/`）
- [x] 端口约定：Vue **5173**，PHP **8091**；Twig 保留 **8090** 至切换完成
- [x] 技术栈：Vue 3 + TS + Vite + Router + Pinia + axios
- [x] **UI 库：Naive UI**
- [x] **生产 base：`/app/`**（`http://host:8091/app/`）
- [x] 独立拷贝：`scripts/install.ps1` + `scripts/serve.ps1`
- [x] 冻结规则：Twig 不再做大改；对照实现以 8090 为准

---

## 阶段 1：后端镜像 + Bootstrap API ✅

### 1.1 从 `php-backend` 同步到 `vue-php/backend`

- [x] `SampleImport.php` / `ReviewImport` 运费导入模式
- [x] `ProductionFact.php` + `FactProvider`（`store_id` 生产库取数）
- [x] `MeichongRules` / `MappingUtils` / `SchemaService` / `DailyReport` 等
- [x] 路由：样品/运费 template+import、JSON generate
- [x] `bin/api_smoke_test.py`（默认 8091）

### 1.2 新增 SPA 读接口

- [x] `GET /api/session`
- [x] `POST /api/session/account` / `POST /api/session/store`
- [x] `GET /api/mappings/bootstrap`
- [x] `GET /api/daily/bootstrap`
- [x] `GET /api/dashboard/bootstrap`
- [x] `Services/PageBootstrap.php`
- [ ] Twig `PagesController` 改为调用 `PageBootstrap`（可选，8090 对照版）

### 1.3 已有写接口（Vue 直接复用，回归即可）

- [x] `POST /api/generate`（需 `store_name`，从 session/bootstrap 取）
- [x] 映射 CRUD / report-fields order（Vue 已接 MappingModal 简化版 + DailyFieldsModal 排序）
- [ ] formula-lines 专用 UI（公式行编辑弹窗未迁）
- [x] `GET/PUT /api/data-sources/{id}/settings`
- [x] 刷单 / 运费 / 样品 template + import
- [x] `PATCH /api/report-runs/{run_id}/values/{value_id}`
- [x] `GET /daily/{id}/export`、SKU 导出（URL 跳转）

---

## 阶段 2：Vue 基建 ✅

- [x] Vite + Vue 3 + TS + Router + **Naive UI** + Pinia
- [x] `api/client.ts`（`withCredentials`）
- [x] `stores/session.ts` + `AppLayout`（导航、店铺/账号切换）
- [x] 路由 + **base `/app/`**
- [x] 迁入 `style.css` + `app.css` 布局覆盖
- [x] 生产 build → `backend/public/app/` + **SPA fallback**（`index.php`）
- [x] `scripts/install.ps1` / `scripts/serve.ps1` 独立部署
- [x] 公共组件：`FieldTypeTag` / `RuleSummary` / `DsSettingsCard` / `MappingModal`（简化）/ `DailyFieldsModal` / `TemplateDownloadModal` / `AccountMenu`

---

## 阶段 3：页面迁移 🟡 ~85%

**顺序：概览 → 报表配置 → 日报输出**（易 → 难）

### 3.1 概览 `/` ✅

- [x] 对齐 `dashboard.html.twig`：Hub 卡片、当前店铺、快捷入口
- [x] 导航高亮、账号切换下拉
- [x] browser-act 截图验收 → `tmp-ui-test-vue/01-dashboard.png`

### 3.2 报表配置 `/mappings` 🟡

- [x] 顶栏：店铺切换（AppLayout）、导出 JSON、「日报字段」按钮
- [x] `DsSettingsCard`：主表/Sheet/日期列、保存（**缺**：定时出报 Schedule 弹窗）
- [x] `ReportFieldsTable`：类型标签、规则摘要、编辑操作列（21 字段）
- [ ] `AuxFieldsTable`：基础取数字段折叠区
- [ ] `ReviewSettingsModal`：刷单 + 物流费规则
- [ ] `ScheduleSettingsModal`
- [x] **`MappingModal`**（简化版：显示名/行代码/格式/多 part 取数；**缺** catalog 级联、公式/比例/每单专用 UI）
- [x] 对照 8090：规则摘要一致；打开取数弹窗 ✅（`03-mapping-modal.png`）

### 3.3 日报输出 `/daily` 🟡

- [x] **Daily Hub 三步**：选日期 → 辅助数据（模板/刷单/运费/样品）→ 生成导出
- [x] 店铺切换（AppLayout）、`default_report_date`、已生成 run 状态条
- [x] `POST /api/generate` + 自动下载 Excel
- [x] `DailyFieldsModal`：字段列表、↑↓ 排序、`PATCH` 数值（**缺**拖拽、改标签、内联表格编辑器）
- [x] `TemplateDownloadModal`（刷单/运费/样品模板）
- [x] `run_id` query 深链
- [ ] 对照 8090 + `bin/compare_runs.php` 数值（可选）

---

## 阶段 4：收尾与切换 🟡 部分

- [ ] `8090` Twig 路由改为 302 → 生产 `/app/`
- [x] README：构建、部署、环境变量（`vue-php/README.md`）
- [ ] 删除或归档 `vue-php/backend/templates` 与旧 static（若不再托管 Twig）
- [x] 全链路回归清单（见下「验收 Checklist」— API + UI 已跑）
- [ ] 文档标记：**Vue 为 PHP 默认前端**

---

## 验收 Checklist（切换前必跑）

### API（脚本）

```powershell
python vue-php\backend\bin\api_smoke_test.py
# → 19 passed @ http://127.0.0.1:8091
```

- [x] 三页面 GET 200（`/app/` SPA）
- [x] settings / report-lines / catalog / schema
- [x] 刷单 / 运费 / 样品模板下载
- [x] `POST /api/generate` + `POST /daily/generate` JSON
- [x] `/api/daily/bootstrap?run_id=` 可读

### UI（browser-act @ build 后 `/app/`）

- [x] 概览：导航、账号、店铺 Hub → `01-dashboard.png`
- [x] 报表配置：主表设置、21 字段表、规则摘要、MappingModal 打开 → `02-mappings.png` `03-mapping-modal.png`
- [x] 日报输出：三步 hub、日报字段弹窗、下载模板弹窗 → `04-daily.png` `05-template-modal.png` `06-daily-fields-modal.png`
- [x] 导入入口可见（刷单 / 运费 / 样品）
- [x] 截图存档 `tmp-ui-test-vue/`

### 出报正确性（可选）

- [ ] `php bin/compare_runs.php <date> <php_run> <python_run>`

---

## 新增 Vue 组件清单

| 组件 | 路径 | 状态 |
|------|------|------|
| AccountMenu | `frontend/src/components/AccountMenu.vue` | ✅ |
| DsSettingsCard | `frontend/src/components/DsSettingsCard.vue` | ✅ 基础 |
| FieldTypeTag | `frontend/src/components/FieldTypeTag.vue` | ✅ |
| RuleSummary | `frontend/src/components/RuleSummary.vue` | ✅ |
| MappingModal | `frontend/src/components/MappingModal.vue` | 🟡 简化 |
| DailyFieldsModal | `frontend/src/components/DailyFieldsModal.vue` | 🟡 无拖拽 |
| TemplateDownloadModal | `frontend/src/components/TemplateDownloadModal.vue` | ✅ |
| useCatalog | `frontend/src/composables/useCatalog.ts` | ✅ |
| useMessage | `frontend/src/composables/useMessage.ts` | ✅ |

---

## 风险

| 风险 | 对策 |
|------|------|
| `vue-php/backend` 落后于 `php-backend` | 定期 robocopy 镜像 |
| Twig 与 Vue 双份页面逻辑 | `PageBootstrap` 单点组装 |
| `mapping_modal.js` 体量大 | composable 拆分；**当前为简化 Modal，后续迭代补全** |
| Cookie 跨端口 | 开发 Vite proxy；生产同源 `/app/` |
| 长期双轨 | 8090 302 → `/app/` 后下线 Twig |

---

## 相关文档

- [Vue前端迁移计划.md](./Vue前端迁移计划.md) — 架构与分阶段说明
- [../README.md](../README.md) — 启动与端口
- 参考实现：`php-backend/templates/` + `public/static/`（8090 已对齐 Python）

---

*最后更新：2026-07-09（阶段 3 核心完成，browser-act + API 19/19 通过）*
