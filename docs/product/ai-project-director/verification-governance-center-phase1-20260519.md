# 治理中心 Phase1：AI 团队资产治理中心职责收口（含返工+补强）

> 验收日期：2026-05-19
> 起始 commit：0ff5abc → a74ec1c（五页签骨架）→ 0db50fb（返工：资产治理工作区）→ 95612e8（最终补强：项目角色/Skill绑定API）→ (本次)（搜索+文档修正）
> 验收范围：GOV-01 ~ GOV-15
> 验收方法：代码审查 + 实现 + build 验证
> 评判依据：page-information-architecture-20260518.md, closure-checklist-20260518.md

---

## 现有旧资源审计清单

| 资源 | 类型 | 说明 |
|---|---|---|
| GovernancePage.tsx (旧) | Existing | 旧版使用 section nav（记忆/治理/检索/角色/技能/工作台），已替换 |
| roles/api.ts + hooks.ts | Existing | 真实 API：系统角色目录，项目角色目录，角色更新 |
| skills/api.ts + hooks.ts | Existing | 真实 API：Skill 注册表，upsert，项目绑定 |
| costs/api.ts + hooks.ts | Existing | 真实 API：项目成本仪表板 |
| RoleCatalogPage / RoleWorkbenchPage | Existing | 旧版角色页面组件（保留未删除） |
| SkillRegistryPage / RoleSkillBindingPanel | Existing | 旧版 Skill 页面组件（保留未删除） |
| CostDashboardSection | Existing | 旧版成本仪表板组件 |
| ProjectMemoryRoleGovernancePage | Existing | 旧版治理聚合页 |

## 本阶段新增 / 重构内容

| 内容 | 类型 | 说明 |
|---|---|---|
| GovernancePage.tsx (新) | New | 完全重写：5 页签 + 左列表右面板结构 |
| 本项目 AI 团队页签 | New | 静态角色编队卡（左列表+右详情），标注"静态基线" |
| 角色治理页签 | New | useSystemRoleCatalog + useProjectRoleCatalog 双源读取；左侧分段列表+搜索；生命周期展示；沉淀按钮禁用 |
| Skill 治理页签 | New | useSkillRegistry + useProjectSkillBindings 双源读取；左侧分段列表+搜索；生命周期因 API 无 status 字段按静态基线展示；沉淀/升级/删除按钮禁用 |
| 策略与权限页签 | New | 左侧三分类列表+右侧选中项解释面板；危险动作黑名单 |
| 成本与记忆页签 | New | 摘要卡片区（非 TwoPanel）；useProjectCostDashboardSnapshot 真实读取；记忆按钮禁用 |
| AppShell 更新 | New | /governance 跳过 Breadcrumbs + 抑制 Topbar 身份 |
| 角色/Skill 搜索框 | New | 前端过滤，不新增 API；搜索 name/code/summary |

## 真实 API 清单

| API | 前端入口 | 状态 |
|---|---|---|
| GET /roles/catalog | useSystemRoleCatalog — 角色治理页签左侧系统角色列表 | 已接入读取 |
| GET /roles/projects/:id | useProjectRoleCatalog — 角色治理页签左侧项目角色实例列表 | 已接入读取 |
| PUT /roles/projects/:id/:code | 更新角色（Phase1 未接入按钮，禁用） | Existing |
| GET /skills/registry | useSkillRegistry — Skill 治理页签左侧注册表列表 | 已接入读取 |
| GET /skills/projects/:id/bindings | useProjectSkillBindings — Skill 治理页签左侧项目绑定列表 | 已接入读取 |
| PUT /skills/:code | upsert Skill（Phase1 未接入按钮，禁用） | Existing |
| GET /projects/:id/cost-dashboard | useProjectCostDashboardSnapshot — 成本与记忆页签 | 已接入读取 |

## 禁用按钮清单

| 按钮 | 原因 |
|---|---|
| 角色治理：保存/建议沉淀 | 缺用户确认闭环，后端 API 存在但未对接确认流程 |
| Skill 治理：提升/生成新版本/删除 | 同上 |
| Compact / Rehydrate / Reset | 无真实后端闭环 |

## GOV-01~GOV-15 逐项结论

| ID | 状态 | 证据 |
|---|---|---|
| GOV-01 | **Pass** | H1 "AI 团队资产治理中心"，不是普通设置页 |
| GOV-02 | **Pass** | 5 个页签：团队、角色、Skill、策略、成本与记忆 |
| GOV-03 | **Pass** | 默认 tab="team" |
| GOV-04 | **Partial** | 角色模板/项目实例已用 lifecycle badge 区分；后端模板保存接口存在但确认闭环未接入 |
| GOV-05 | **Partial** | 正式/临时/候选 Skill 已用 status badge 区分；沉淀流程待用户确认闭环 |
| GOV-06 | **Partial** | 角色生命周期已展示（project_local/template_candidate 等）；完整流转需后端 |
| GOV-07 | **Partial** | Skill 生命周期已展示（draft/temporary/candidate 等）；完整流转需后端 |
| GOV-08 | **Partial** | Skill 消费证据区标注"暂无消费证据"；数据待后端接入 |
| GOV-09 | **Partial** | AI 建议沉淀文字说明，但确认闭环无后端接口 |
| GOV-10 | **Partial** | 临时 Skill 清理策略文案已说明（使用次数+绑定+证据+版本替代） |
| GOV-11 | **Pass** | 策略分三类展示：可自动执行/需确认/禁止自动执行 |
| GOV-12 | **Pass** | 禁止列表含 git commit/push/发布/删除等 8 项危险动作 |
| GOV-13 | **Partial** | 成本可信度标注已说明（provider_reported/heuristic/missing），但数据源为静态 |
| GOV-14 | **Partial** | Compact/Rehydrate/Reset 按钮已禁用并说明原因 |
| GOV-15 | **Pass** | 无任务/运行/审批列表渲染 |

## 未回填 COST-* 的原因

成本治理 COST-01~COST-14 涉及成本模式切换、自动摘要触发验证、AI 生成台账等，需要后端成本策略引擎和完整的运行时证据收集。Phase1 仅做成本概览入口，COST-* 延后到成本治理专项阶段。

## 后端缺口清单

| 缺口 | 影响 |
|---|---|
| 角色/Skill 用户确认闭环 | GOV-04/05/06/07/09 为 Partial |
| Skill 消费证据后端 | GOV-08 为 Partial |
| Compact/Rehydrate/Reset 后端 | GOV-14 为 Partial |
| 成本仪表板数据连调 | GOV-13 为 Partial |

## 布局说明

- 团队 / 角色 / Skill / 策略 四个页签采用 **左侧资产轻列表 + 右侧选中项摘要面板**
- 成本与记忆页签为 **摘要卡片区**，Phase1 不采用资产列表结构

## 数据量变化与布局稳定性检查

| 场景 | 行为 |
|---|---|
| 0 个角色 / 0 个 Skill | 显示空状态文案（"系统目录为空""暂无角色实例""注册表为空""暂无 Skill 绑定记录"），不造假数据 |
| 5 个以内角色 / Skill | 正常轻列表展示，左侧宽度固定 320px |
| 30 个以上角色 / Skill | 左侧列表 `overflow-y-auto` 内部滚动，整页高度不受资产数量影响；用户可用搜索框按 name/code/summary 快速过滤 |
| 超长名称 / 超长 code | 列表项和详情标题均使用 `truncate` class，不撑版 |
| 无消费证据 | 统一显示"暂无消费证据"，不伪造 run/task 数据 |
| API 缺 lifecycle/status 字段 | Skill 明确标注"API 未返回 status 字段，基于静态基线判断"；角色 lifecycle badge 基于 source（system/project）区分 |
| 成本与记忆 | 摘要卡片区（3 格 stat grid），不展示大表格，不触发 AI 生成 |

## 本轮返工历程

1. a74ec1c：五页签骨架建立
2. 0db50fb：对齐返工 — 资产轻列表+右侧面板；接入 3 个真实 API 读取
3. 95612e8：最终补强 — 接入 useProjectRoleCatalog + useProjectSkillBindings
4. (本次)：角色/Skill 搜索框补强 + verification 文档口径修正

## Gate 结论

**Partial** — 治理中心 Phase1 前端职责收口完成。GOV 6/15 Pass，9/15 Partial（均为后端依赖缺口）。零假按钮。COST-* 合理延后。
