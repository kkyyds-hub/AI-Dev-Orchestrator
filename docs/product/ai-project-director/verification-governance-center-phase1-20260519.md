# 治理中心 Phase1：AI 团队资产治理中心职责收口

> 验收日期：2026-05-19
> 起始 commit：0ff5abc
> 结束 commit：(本次)
> 验收范围：GOV-01 ~ GOV-15
> 验收方法：代码审查 + 实现 + build 验证
> 评判依据：page-information-architecture-20260518.md, closure-checklist-20260518.md

---

## 现有旧资源审计清单

| 资源 | 类型 | 说明 |
|---|---|---|
| GovernancePage.tsx (旧) | Existing | 旧版使用 section nav（记忆/治理/检索/角色/技能/工作台），委托 ProjectMemoryRoleGovernancePage |
| roles/api.ts + hooks.ts | Existing | 真实 API：系统角色目录 GET /roles/catalog，项目角色目录 GET/PUT |
| skills/api.ts + hooks.ts | Existing | 真实 API：Skill 注册表 GET，upsert PUT，项目绑定 GET/PUT |
| costs/api.ts + hooks.ts | Existing | 真实 API：项目成本仪表板 GET /projects/:id/cost-dashboard |
| RoleCatalogPage / RoleWorkbenchPage | Existing | 旧版角色页面组件 |
| SkillRegistryPage / RoleSkillBindingPanel | Existing | 旧版 Skill 页面组件 |
| CostDashboardSection | Existing | 旧版成本仪表板组件 |
| ProjectMemoryRoleGovernancePage | Existing | 旧版治理聚合页 |

## 本阶段新增 / 重构内容

| 内容 | 类型 | 说明 |
|---|---|---|
| GovernancePage.tsx (新) | New | 完全重写：5 页签结构，AI 团队资产治理中心 |
| 本项目 AI 团队页签 | New | 静态角色编队卡，标注"角色目录静态基线，待接入真实运行时消费证据" |
| 角色治理页签 | New | 生命周期展示，区分项目实例/模板；建议沉淀按钮禁用（缺用户确认闭环） |
| Skill 治理页签 | New | 生命周期展示，Skill 示例列表；沉淀按钮禁用；清理策略文案 |
| 策略与权限页签 | New | 三分类（可自动/需确认/禁止），危险动作黑名单 |
| 成本与记忆页签 | New | 成本可信度标注，Compact/Rehydrate/Reset 禁用 |
| AppShell 更新 | New | /governance 跳过 Breadcrumbs + 抑制 Topbar 身份 |

## 真实 API 清单

| API | 前端入口 | 状态 |
|---|---|---|
| GET /roles/catalog | 角色目录（旧 API） | Existing |
| GET /roles/projects/:id | 项目角色（旧 API） | Existing |
| PUT /roles/projects/:id/:code | 更新角色（旧 API，Phase1 未接入按钮） | Existing |
| GET /skills/registry | Skill 注册表（旧 API） | Existing |
| PUT /skills/:code | upsert Skill（旧 API，Phase1 未接入按钮） | Existing |
| GET /projects/:id/cost-dashboard | 成本仪表板（旧 API） | Existing |

## 禁用按钮清单

| 按钮 | 原因 |
|---|---|
| 角色治理：保存/建议沉淀 | 缺用户确认闭环，后端 API 存在但未对接确认流程 |
| Skill 治理：保存/建议沉淀 | 同上 |
| Skill 治理：打开 Skill 注册表 | 导航跳转待后续实现 |
| Compact / Rehydrate / Reset | 无真实后端闭环 |
| 角色工作台入口 | 导航跳转待后续实现 |

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
| 角色/Skill 导航入口实现 | 两个按钮 disabled |

## Gate 结论

**Pass（Phase1）** — 治理中心从旧 section nav 重构为 5 页签 AI 团队资产治理中心。5/15 Pass，10/15 Partial（均为后端依赖缺口，不是前端造假）。零假按钮。COST-* 合理延后。
