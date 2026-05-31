# 阶段 3：项目页 AI 总结按钮现状审计

> 文档类型：Stage 3 project AI summary button capability audit
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`659f4b3`
> 前置阶段：R1-P RC Pass（AI Project Director Release Candidate）

---

## 1. 审计范围

检查当前代码库是否已有项目级 AI 总结相关的：
- 后端 API
- 前端入口
- 数据聚合能力
- 保存 / 过期 / readback 机制
- 三层信息模型支持

---

## 2. 当前能力清单

### 2.1 已有：Run 级 AI 摘要（RunAISummary）

| 组件 | 状态 | 位置 |
|---|---|---|
| RunAISummary domain | ✅ 存在 | `app/domain/run_ai_summary.py` |
| RunAISummaryType 枚举 | ✅ 含 PROJECT 定义（但未使用） | `RunAISummaryType.PROJECT` |
| RunAISummarySource 枚举 | ✅ AI / RULE_FALLBACK | `RunAISummarySource` |
| RunAISummaryStatus | ✅ PENDING / SUCCEEDED / FAILED | — |
| source_hash / source_version | ✅ 已有 | RunAISummary model |
| stale flag | ✅ 已有 | RunAISummary model |
| RunAISummaryRepository | ✅ 存在 | `repositories/run_ai_summary_repository.py` |
| RunAISummaryService | ✅ 存在 | `services/run_ai_summary_service.py` |
| Run API: GET /runs/{id}/ai-summary | ✅ 存在 | `routes/runs.py` |
| Run API: POST /runs/{id}/ai-summary/generate | ✅ 存在 | `routes/runs.py` |
| Run API: POST /runs/{id}/ai-summary/regenerate | ✅ 存在 | `routes/runs.py` |
| Run API: GET /runs/{id}/ai-summaries (history) | ✅ 存在 | `routes/runs.py` |

**结论：Run 级 AI 摘要基础设施已完备。RunAISummaryType.PROJECT 已在枚举中定义，可直接复用。**

### 2.2 已有：项目页路由与容器

| 组件 | 状态 | 位置 |
|---|---|---|
| ProjectOverviewRouteContainer | ✅ 存在 | `pages/projects/ProjectOverviewRouteContainer.tsx` |
| ProjectOverviewPage | ✅ 存在 | `features/projects/ProjectOverviewPage.tsx` |
| 子视图支持 | ✅ 7 种 (overview/timeline/deliverable/approval/governance/repository/collaboration) | `ProjectOverviewPageView` |

**结论：项目页基础架构已就绪，可新增 AI summary 子视图。**

---

## 3. 缺口清单

### 3.1 后端 API 缺口

| # | 缺口 | 严重度 | 说明 |
|---|---|---|---|
| 1 | 无 `/projects/{id}/ai-summary` GET 端点 | **高** | 需要新增：读取/缓存项目摘要 |
| 2 | 无 `/projects/{id}/ai-summary/generate` POST 端点 | **高** | 需要新增：触发项目摘要生成 |
| 3 | 无 `/projects/{id}/ai-summary/regenerate` POST 端点 | **中** | 需要新增：强制重新生成 |
| 4 | 无项目级聚合服务 | **高** | 需要新增 ProjectAISummaryService，从 task/run/deliverable/approval/risk 聚合数据 |
| 5 | PROJECT 类型摘要未保存 | **中** | RunAISummaryRepository 已支持，但未生成 PROJECT 类型记录 |

### 3.2 前端入口缺口

| # | 缺口 | 严重度 | 说明 |
|---|---|---|---|
| 1 | 无项目页"生成 AI 总结"按钮 | **高** | 需要新增按钮组件 |
| 2 | 无 project-summary feature 模块 | **高** | 需要新增 `features/project-summary/` (api.ts / hooks.ts / types.ts) |
| 3 | 无项目摘要展示面板 | **高** | ProjectOverviewPage 需要新增 AI summary view |
| 4 | 无摘要过期标识 | **中** | 前端应展示 stale badge |

### 3.3 数据聚合字段建议

项目 AI 总结应聚合以下数据（供 prompt builder 使用）：

| 数据源 | 关键字段 | 现有 API |
|---|---|---|
| 项目目标 | project.name, project.summary, goal_text | GET /projects |
| 计划版本 | plan_summary, phases, risks | GET /project-director/plan-versions/{id} |
| 任务状态 | task stats (total/pending/running/completed/failed/blocked) | GET /projects → task_stats |
| Run 摘要 | recent runs with status/summary | GET /tasks/{id}/runs |
| 交付物 | deliverable count, types | GET /deliverables/projects/{id} |
| 审批 | approval statuses, overdue | GET /approvals/projects/{id} |
| 成本 | total_cost, mode_breakdown | GET /projects/{id}/cost-dashboard |
| 角色/Skill | role consumption, skill usage | GET /roles/projects/{id}/consumption |
| 阻塞/风险 | blocking_reasons, risk_notes | ConsoleService → task readiness |

### 3.4 保存与 stale 机制

| 能力 | 当前状态 | 建议 |
|---|---|---|
| summary 保存 | RunAISummaryRepository 已支持 PROJECT type | 复用现有表，summary_type=PROJECT |
| source_hash / stale | RunAISummary 已含字段 | 用 task 数 + run 数 + deliverable 数 + approval count 构建 source_hash |
| 过期判断 | generate_current_summary 已实现 | 复用现有逻辑：数据变更 → hash mismatch → stale |
| readback | GET /runs/{id}/ai-summary 已有模式 | 新建 GET /projects/{id}/ai-summary |
| 缓存复用 | RunAISummaryService 已实现 | 复用 |
| source=rule_fallback | RunAISummarySource.RULE_FALLBACK 已定义 | 后台不可用时使用规则生成 L0 文本摘要 |

---

## 4. 三层信息模型检查

按 `page-information-architecture-20260518.md` 的三层信息模型：

| 层 | 内容 | 当前状态 | 需要 |
|---|---|---|---|
| 用户摘要层 | 项目状态、进度、关键风险、下一步建议 | 无 | AI summary 面板（summary_markdown） |
| 操作建议层 | AI 推荐操作、待确认事项 | 无 | next_action / recommended_actions |
| 技术日志层 | Run 详情、日志、决策回放 | 已有（通过跳转） | 已有 RunsTab，不需重复 |

---

## 5. 风险边界

| # | 风险 | 控制 |
|---|---|---|
| 1 | 页面打开自动触发 AI 生成 | 必须手动按钮触发；不可自动 |
| 2 | 强模型调用无理由记录 | L3 调用需记录理由 |
| 3 | 暴露 provider_receipt / API key | summary 面板默认折叠技术细节 |
| 4 | 数据过期不提示 | stale badge 必须展示 |
| 5 | 假按钮（无后端） | 按钮必须真实调用 POST API |

---

## 6. 下一步建议

### 建议交给 Codex：最小代码补丁

因为：
- RunAISummary 基础设施已完备（domain / repository / service / source_hash / stale）
- RunAISummaryType.PROJECT 已在枚举中定义
- 项目页容器已就绪
- 数据聚合 API 全部存在（project stats / task / deliverable / approval / cost / consumption）

Codex 需要做的最小代码补丁：

1. **后端**：
   - 新增 `GET /projects/{id}/ai-summary`（读取/缓存）
   - 新增 `POST /projects/{id}/ai-summary/generate`（触发生成）
   - 新增 `POST /projects/{id}/ai-summary/regenerate`（强制重新生成）
   - 新增 `ProjectAISummaryService.build_project_context()` 聚合方法
   - 复用 `RunAISummaryRepository` 保存 PROJECT 类型记录

2. **前端**：
   - 新增 `features/project-summary/` (api.ts / hooks.ts / types.ts)
   - 项目页新增"生成 AI 总结"按钮 + 摘要展示面板
   - stale badge 展示
   - source badge（ai / rule_fallback）

### 下一条最小实现指令草案

```
建议使用模型：Codex
任务类型：阶段 3 项目页 AI 总结最小后端 + 前端补丁

请先确认 origin/main 最新提交。
必须读取所有相关文件后再实现。

后端：
1. 在 routes/projects.py 新增三个端点。
2. 新增 ProjectAISummaryService，从 RunAISummaryRepository
   继承 PROJECT type 保存/读取。
3. build_project_context() 聚合 project / task_stats /
   recent_runs / deliverables / approvals / cost / risks。
4. 页面打开不触发 AI 生成。
5. 重用以 RunAISummary 的 source_hash / stale 机制。

前端：
1. 新增 features/project-summary/。
2. 项目页新增按钮 + 摘要面板。
3. 展示 source / stale badge。
4. 按钮必须真实调用 POST。

严格边界：
- 不改其他业务代码
- 不改产品基线
- 不调用 provider_openai / deepseek-v4-pro
- 不调用 Worker Pool
- 不调用 planning/apply
- 不调用 apply-local / git-commit
- 不假按钮
```

---

## 7. 总结表

| 问题 | 答案 |
|---|---|
| 是否已有项目总结 API | **否 — 需要在 projects.py 新增** |
| 是否已有项目页总结按钮 | **否 — 前端需要新增** |
| RunAISummary 基础设施可否复用 | **是 — PROJECT type 已在枚举中，repository/service 可直接复用** |
| 数据聚合是否已具备 | **是 — 各 API 已存在，仅需聚合 service** |
| 是否已有 stale / source_hash 机制 | **是 — RunAISummary 已含，直接复用** |
| 主要缺口 | 后端 3 端点 + 1 service；前端 1 feature + 1 UI 面板 |
| 下一步 | **Codex 最小代码补丁** |
