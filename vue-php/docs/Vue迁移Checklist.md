# Vue 前端迁移 Checklist

> **目标**：PHP 可操作前端从 **Twig + 原生 JS**（`php-backend/` :8090）迁到 **Vue 3 SPA**（`vue-php/frontend/`），后端 **`vue-php/backend/`** :8091。  
> **生产入口**：`http://host:8091/app/`

---

## 当前状态（2026-07-09）

| 工程 | 路径 | 端口 | 前端 | 完成度 |
|------|------|------|------|--------|
| Python 参考 | `app/` | 8081 | Jinja + JS | 100%（主线） |
| Twig PHP（对照） | `php-backend/` | 8090 | **302 → Vue** | API/导出保留，页面已跳转 |
| **Vue + PHP（默认）** | `vue-php/` | 5173 + 8091 | **Vue 3 + Naive UI** | **✅ ~95%** |

**结论**：Vue 为 PHP 默认可操作前端；8090 页面路由 302 到 `/app/`。

---

## 阶段总览

```
[0] 决策 ──► [1] 后端镜像 + Bootstrap API ──► [2] Vue 基建 ──► [3] 页面迁移 ──► [4] 收尾切换
   ✅           ✅                              ✅              ✅              ✅
```

---

## 阶段 0：决策与冻结 ✅

- [x] 独立套件 `vue-php/`
- [x] Naive UI + Pinia + axios `withCredentials`
- [x] 生产 base `/app/`
- [x] `scripts/install.ps1` + `scripts/serve.ps1`

---

## 阶段 1：后端镜像 + Bootstrap API ✅

- [x] `php-backend` → `vue-php/backend` 镜像
- [x] `PageBootstrap.php` + session/mappings/daily/dashboard bootstrap
- [x] 样品/运费/生产库取数/JSON generate
- [x] `api_smoke_test.py` **19/19** @ 8091

---

## 阶段 2：Vue 基建 ✅

- [x] Vite build → `backend/public/app/` + SPA fallback
- [x] `style.css` + `app.css` 布局覆盖
- [x] `AppLayout` 导航 + 账号/店铺切换
- [x] `NDialogProvider` / `NMessageProvider`

---

## 阶段 3：页面迁移 ✅

### 3.1 概览 `/` ✅

- [x] `home-hub` 双卡片 + 最近生成
- [x] 账号/店铺切换
- [x] browser-act → `01-dashboard.png`

### 3.2 报表配置 `/mappings` ✅

- [x] 顶栏：导出 JSON、公式行、日报字段
- [x] `DsSettingsCard`：catalog 级联 + 刷单设置 + 定时出报入口
- [x] `ReportFieldsTable`：21 字段 + 规则摘要 + 配置/删除
- [x] `AuxFieldsTable`：基础取数字段折叠区
- [x] `ReviewSettingsModal`：刷单导入 + 物流费
- [x] `ScheduleSettingsModal`：每日自动生成时间
- [x] `MappingModal`：取数/复用/每单/比例/占位 + parts 级联
- [x] `FormulaModal`：公式行 CRUD
- [x] browser-act → `07-mappings-full.png` `08-mapping-modal-full.png`

### 3.3 日报输出 `/daily` ✅

- [x] `daily-hub` 三步工作流
- [x] 模板下载 / 刷单 / 运费 / 样品导入
- [x] `POST /api/generate` + 自动下载 Excel
- [x] `DailyEditor`：内联表格 + 拖拽/▲▼ 排序 + 改标签 + 改值
- [x] `DailyFieldsModal`：弹窗版编辑器
- [x] `run_id` 深链
- [x] browser-act → `09-daily-editor.png`

---

## 阶段 4：收尾与切换 ✅

- [x] `8090` GET `/`、`/mappings`、`/daily` → 302 `VUE_APP_URL`（默认 `http://127.0.0.1:8091/app`）
- [x] README 标记 Vue 为默认前端
- [x] API + UI 全链路回归
- [x] 截图存档 `tmp-ui-test-vue/`（01～09）

---

## 验收 Checklist ✅

### API

```powershell
python vue-php\backend\bin\api_smoke_test.py
# 19 passed @ http://127.0.0.1:8091
```

- [x] SPA `/app/` 200
- [x] settings / catalog / schema / report-lines
- [x] 刷单 / 运费 / 样品模板
- [x] `POST /api/generate` + `/daily/generate` JSON
- [x] bootstrap API 全绿

### UI（browser-act @ `/app/`）

- [x] 概览 Hub
- [x] 报表配置：DsSettings + 21 字段 + Aux + MappingModal 全 Tab
- [x] 日报：Hub + DailyEditor 内联 + 弹窗
- [x] 导入入口可见

### 可选

- [ ] `php bin/compare_runs.php` 数值对照 Python

---

## Vue 组件清单

| 组件 | 路径 | 状态 |
|------|------|------|
| MappingModal | `components/MappingModal.vue` | ✅ 全 Tab |
| MappingPartBlock | `components/mapping/MappingPartBlock.vue` | ✅ |
| FormulaModal | `components/FormulaModal.vue` | ✅ |
| ReviewSettingsModal | `components/ReviewSettingsModal.vue` | ✅ |
| ScheduleSettingsModal | `components/ScheduleSettingsModal.vue` | ✅ |
| DsSettingsCard | `components/DsSettingsCard.vue` | ✅ |
| AuxFieldsTable | `components/AuxFieldsTable.vue` | ✅ |
| DailyEditor | `components/DailyEditor.vue` | ✅ 拖拽+编辑 |
| DailyFieldsModal | `components/DailyFieldsModal.vue` | ✅ |
| RuleSummary / FieldTypeTag | `components/` | ✅ |

---

## 已知差异（非阻塞）

- MappingModal 未实现 Twig 版「嵌套弹窗栈」与高级 filters/join 全 UI（API 已支持，可按需迭代）
- 8090 仍保留 API/导出路由，session 切换 POST 仍走 8090（生产建议统一 8091）

---

*最后更新：2026-07-09 — 迁移完成，Vue 为默认前端*
