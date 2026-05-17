# 后端项目级页面数据闭环缺口台账

> 审计日期: 2026-05-17
> main 基线: e82d146d0e3aaebbf1c40eeae72f3e5330fb7a2f
> 审计范围: 仓库页、交付物页、审批页、治理页、项目总览页的完整后端数据链路
> 审计方式: 只读追踪，未修改任何代码

---

## 一、总体结论

| 分类 | 数量 |
|---|---|
| 已闭环（数据从真实后端生成） | 5 项 |
| 接口存在但空（需要上游写链路） | 4 项 |
| DTO 断层（字段存在但未序列化） | 2 项 |
| 无自动生成闭环（数据需要手动创建） | 2 项 |
| 前端壳（纯展示，数据源健康） | 6 项 |
| 不确定 | 0 项 |

### 最关键发现

1. **交付件和审批数据完全依赖手动创建** —— 后端没有任何从 task/run/change-batch 自动生成交付件或审批记录的代码。
2. **仓库页数据链路线完整** —— 14+ API 端点都按 projectId 过滤，数据来自真实文件系统/DB。
3. **治理页数据大部分已有** —— 角色/技能/绑定有自动种子，记忆有刷新，但治理巡检点依赖 worker 写入。
4. **项目总览数据健全** —— 每 5 秒轮询所有项目和任务，DTO 字段丰富。

---

## 二、逐页审计明细

### A. 仓库工作区 (RepositoryOverviewPage)

**前端入口:** `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`

| 数据项 | 前端 hook/API | 后端 route | 后端 service | 存储 | 当前状态 |
|---|---|---|---|---|---|
| repository_workspace | 嵌入 `project`/`detail` props | 嵌入 `/console/project-overview` `/projects/{id}` | `RepositoryWorkspaceRepository` | `repository_workspaces` 表 | ✅ 已闭环 |
| latest_repository_snapshot | `useRefreshProjectRepositorySnapshot(pid)` | `POST /repositories/projects/{pid}/snapshot/refresh` | `RepositoryScanService.scan_project_repository()` | `repository_snapshots` 表 | ✅ 已闭环 |
| current_change_session | `useProjectChangeSession(pid)` `useCaptureProjectChangeSession(pid)` | `GET/POST /repositories/projects/{pid}/change-session` | `BranchSessionService` | `change_sessions` 表 | ✅ 已闭环 |
| change_plans | `useProjectChangePlans({projectId})` | `GET /planning/projects/{pid}/change-plans` | `ChangePlanService.list_change_plans()` | `change_plans` 表 | ✅ 已闭环 |
| change_batches | `useProjectChangeBatches(pid)` | `GET /repositories/projects/{pid}/change-batches` | `ChangeBatchService.list_change_batches()` | `change_batches` 表 | ✅ 已闭环 |
| verification_baseline | `useProjectRepositoryVerificationBaseline(pid)` | `GET /repositories/projects/{pid}/verification-baseline` | `RepositoryVerificationService.get_or_create_project_baseline()` | `verification_templates` 表 (自动种子) | ✅ 已闭环 |
| verification_runs | `useProjectVerificationRuns(pid)` | `GET /runs/verification/projects/{pid}` | `VerificationRunService.get_project_feed()` | `verification_runs` 表 | ✅ 已闭环 |
| diff_summary / change_evidence | `useProjectChangeEvidence(pid)` | `GET /deliverables/projects/{pid}/change-evidence` | `DiffSummaryService.get_project_change_evidence()` | 跨 `change_batches` + `verification_runs` + `deliverable_versions` | ✅ 已闭环 |
| commit_candidate | `useProjectCommitCandidates(pid)` `useGenerateChangeBatchCommitCandidate(pid, bid)` | `GET /repositories/projects/{pid}/commit-candidates` `POST /repositories/change-batches/{bid}/commit-candidate` | `CommitCandidateService` | `commit_candidates` 表 | ✅ 已闭环 |
| file_locator | `useProjectFileLocatorSearch(pid)` | `POST /repositories/projects/{pid}/file-locator/search` | `CodebaseLocatorService.locate_files()` | 文件系统扫描 | ✅ 已闭环 |
| context_pack | `useBuildProjectCodeContextPack(pid)` | `POST /repositories/projects/{pid}/context-pack` | `ContextBuilderService.build_code_context_pack()` | 文件系统读取 | ✅ 已闭环 |
| release_gate | `useDay15ReleaseJudgement(pid)` | `GET /approvals/projects/{pid}/day15-release-judgement` | `RepositoryReleaseGateService` | `change_batches` + 多表 | ✅ 已闭环 |
| day15_flow | `useRepositoryDay15Flow(pid)` | `GET /repositories/projects/{pid}/day15-flow` | `build_repository_day15_flow_snapshot()` | `projects` + `change_batches` + `repository_snapshots` + git 工作区 | ✅ 已闭环 |

**project_id 过滤:** 所有端点均通过 URL 路径参数 `{pid}` 过滤。基于 ID 的端点（`change_plan_id`, `change_batch_id`）不直接进行 project_id 检查，但服务层验证了所有权。

**仓库页结论: 全线已闭环，无后端数据缺口。**

---

### B. 交付物中心 (DeliverablesPage / DeliverableCenterPage)

**前端入口:** `apps/web/src/pages/deliverables/DeliverablesPage.tsx` → `apps/web/src/features/deliverables/DeliverableCenterPage.tsx`

| 数据项 | 前端 hook/API | 后端 route | 后端 service | 存储 | 当前状态 |
|---|---|---|---|---|---|
| 项目交付物列表 | `useProjectDeliverableSnapshot(pid)` | `GET /deliverables/projects/{pid}` | `DeliverableService.get_project_deliverable_snapshot(pid)` → `DeliverableRepository.list_records_by_project_id(pid)` | `deliverables` + `deliverable_versions` 表 | 🔴 **接口存在但空** |
| 交付物详情 | `useDeliverableDetail(did)` | `GET /deliverables/{did}` | `DeliverableService.get_deliverable_detail(did)` → `DeliverableRepository.get_record_by_id(did)` | `deliverables` 表 | 🔴 **接口存在但空** |
| 交付物创建 | `useCreateDeliverable(pid)` | `POST /deliverables` | `DeliverableService.create_deliverable()` | `deliverables` 表 (INSERT) | 🔴 **缺写入** |
| 变更证据 | `useProjectChangeEvidence(pid)` | `GET /deliverables/projects/{pid}/change-evidence` | `DiffSummaryService.get_project_change_evidence()` | 跨表组合 | 🟡 **依赖上游数据** |

**根因分析:**

`DeliverableService.create_deliverable()` 仅在收到显式 `POST /deliverables` 请求时才创建。后端代码中:
- `E:\new-AI-Dev-Orchestrator-push\runtime\orchestrator\app\services\deliverable_service.py:112` — `create_deliverable()` 手动调用
- `E:\new-AI-Dev-Orchestrator-push\runtime\orchestrator\app\services\project_stage_service.py` — 不调用 `DeliverableService`
- `E:\new-AI-Dev-Orchestrator-push\runtime\orchestrator\app\workers\task_worker.py` — 不调用 `DeliverableService`

**无任何自动化闭环**从 task/run/change-batch 生成交付件。

E2E 测试 (`smoke_backend_real_e2e_plane_star_wars.py:601-614`) 通过直接调用 `POST /deliverables` 来手动创建交付件。

**修复建议:**
- P0: 在 worker run 完成后的 `_finalize_execution()` 或 token accounting 后，自动为成功的 provider run 创建交付件快照
- P0: 在 change plan 创建后，自动关联交付件

---

### C. 审批中心 (ApprovalsPage / ApprovalInboxPage)

**前端入口:** `apps/web/src/pages/approvals/ApprovalsPage.tsx` → `apps/web/src/features/approvals/ApprovalInboxPage.tsx`

| 数据项 | 前端 hook/API | 后端 route | 后端 service | 存储 | 当前状态 |
|---|---|---|---|---|---|
| 项目审批列表 | `useProjectApprovalInbox(pid)` | `GET /approvals/projects/{pid}` | `ApprovalService.get_project_inbox(pid)` → `ApprovalRepository.list_records_by_project_id(pid)` | `approval_requests` 表 | 🔴 **接口存在但空** |
| 审批详情 | `useApprovalDetail(aid)` | `GET /approvals/{aid}` | `ApprovalService.get_approval_detail(aid)` | `approval_requests` + `approval_decisions` 表 | 🔴 **接口存在但空** |
| 审批创建 | `useCreateApprovalRequest(pid)` | `POST /approvals` | `ApprovalService.request_deliverable_approval()` | `approval_requests` 表 (INSERT) | 🔴 **缺写入** |
| 审批决策 | `useApplyApprovalAction(aid)` | `POST /approvals/{aid}/actions` | `ApprovalService.apply_approval_decision()` | `approval_decisions` 表 (INSERT) | 🔴 **缺写入** |
| 审批历史 | `useApprovalHistory(aid)` | `GET /approvals/{aid}/history` | `ApprovalService.get_approval_history(aid)` | `approval_requests` + `deliverable_versions` | 🔴 **依赖上游数据** |

**根因分析:**

`ApprovalService.request_deliverable_approval()` (`approval_service.py:167`) 仅从 `POST /approvals` 路由调用。需要:
1. 先有交付件（`DeliverableRepository.get_record_by_id(deliverable_id)` 返回数据）
2. 交付件有版本 (`deliverable.current_version_number > 0`)
3. 用户手动调用 POST

**无任何自动化闭环**生成审批记录。

此外，`ApprovalInboxPage.tsx` 的合格交付件列表依赖 `deliverableSnapshotQuery.data?.deliverables`，而交付件列表已经是空的，因此审批创建表单的 `<select>` 永远为空。

**修复建议:**
- P0: 先修复交付件生成（见 B 节）
- P1: 在 release gate approve 后，自动创建审批记录
- P1: 在 commit candidate 创建后，自动发起交付件审批

---

### D. 治理中心 (GovernancePage / ProjectMemoryRoleGovernancePage)

**前端入口:** `apps/web/src/pages/governance/GovernancePage.tsx` → `apps/web/src/features/projects/pages/ProjectMemoryRoleGovernancePage.tsx`

| 数据项 | 前端 hook/API | 后端 route | 后端 service | 存储 | 当前状态 |
|---|---|---|---|---|---|
| 项目记忆快照 | `useProjectMemorySnapshot(pid)` | `GET /projects/{pid}/memory` | `ProjectMemoryService.get_project_memory_snapshot(pid, refresh=True)` | 文件 JSON (从 `projects/tasks/runs/deliverables/approvals/failure_reviews` 刷新) | 🟡 **数据源有效但刷新代价高** |
| 记忆检索 | `useProjectMemorySearch(pid, q)` | `GET /projects/{pid}/memory/search` | `ProjectMemoryService.search_project_memories()` | 刷新后词法搜索 | 🟡 **数据源有效** |
| 治理状态 | `useMemoryGovernanceState(pid)` | `GET /projects/{pid}/memory/governance` | `ProjectMemoryService.get_memory_governance_state(pid)` | 文件 JSON (`project-memory-governance/` 目录) | 🟡 **接口存在但空（需 worker 写入）** |
| 治理动作 (rehydrate/compact/reset) | `useMemoryGovernanceRehydrate` 等 | `POST /projects/{pid}/memory/governance/rehydrate` 等 | `ProjectMemoryService.rehydrate_context()` 等 | 文件 JSON 写盘 | 🟡 **可手动触发，但需要记忆数据非空** |
| 系统角色目录 | `useSystemRoleCatalog()` | `GET /roles/catalog` | `RoleCatalogService.list_system_role_catalog()` | 硬编码 4 个 Python 常量 | ✅ 已闭环 |
| 项目角色配置 | `useProjectRoleCatalog(pid)` | `GET /roles/projects/{pid}` | `RoleCatalogService.get_project_role_catalog(pid)` 自动种子 | `project_roles` 表 | ✅ 已闭环 |
| 角色工作台 | `useRoleWorkbenchSnapshot(pid)` | `GET /console/role-workbench?project_id={pid}` | `ConsoleService.get_role_workbench(pid)` | `tasks` + `runs` + 日志文件 handoff 解析 | 🟡 **数据有效但日志依赖脆弱** |
| 技能注册表 | `useSkillRegistry()` | `GET /skills/registry` | `SkillRegistryService.list_skill_registry()` 自动种子 12 个技能 | `skills` + `skill_versions` 表 | ✅ 已闭环 |
| 项目技能绑定 | `useProjectSkillBindings(pid)` | `GET /skills/projects/{pid}/bindings` | `SkillRegistryService.get_project_skill_bindings(pid)` 自动种子 | `skill_role_bindings` 表 | ✅ 已闭环 |

**治理页结论:**

- **角色/技能/绑定:** ✅ 自动种子，首次访问即有数据
- **记忆快照:** 🟡 需要项目有 tasks/runs/deliverables 才有内容；刷新代价高（每次都全量扫描 5+ 表）
- **治理巡检点/回收:** 🔴 需要 worker 主动写入 `project-memory-governance/` 目录；新项目为空
- **角色工作台 handoff:** 🟡 从日志文件解析，日志缺失则该字段为空

---

### E. 项目总览 (ProjectOverviewPage)

**前端入口:** `apps/web/src/features/projects/ProjectOverviewPage.tsx` → `useProjectOverviewPageController.ts`

| 数据项 | 前端 hook/API | 后端 route | 后端 service | 存储 | 当前状态 |
|---|---|---|---|---|---|
| 项目总览 | `useBossProjectOverview()` | `GET /console/project-overview` | `ConsoleService.get_project_overview()` | `projects` + `tasks` + `runs` 全表扫描 | ✅ 已闭环 |
| 项目详情 | `useProjectDetail(pid)` | `GET /projects/{pid}` | `ProjectService.get_project_detail(pid)` | `projects` + `tasks` + `runs` + 阶段守卫 | ✅ 已闭环 |
| Day15 仓库流 | `useProjectDay15FlowOverview(pid)` | `GET /projects/{pid}/day15-repository-flow` | `build_repository_day15_flow_snapshot(pid)` | `projects` + `change_batches` + `repository_snapshots` + git 工作区 | ✅ 已闭环 |
| 阶段推进 | `useAdvanceProjectStage(pid)` | `POST /projects/{pid}/advance-stage` | `ProjectStageService.advance_project_stage(pid)` | `projects` 表 (更新 stage, stage_history_json) | ✅ 已闭环 |
| 钻取任务详情 | inline query | `GET /tasks/{tid}/detail` | `ConsoleService.get_task_detail(tid)` | `tasks` + `runs` 表 | ✅ 已闭环 |

**项目总览结论: 全线已闭环，无后端数据缺口。**

注意点:
- `GET /console/project-overview` 每 5 秒轮询，全量扫描 `projects` + `tasks` + `runs` —— 项目数大时可能变慢
- `GET /projects/{pid}` 的 `current_change_session` 在 DTO 构造时硬编码为 `None` (`projects.py:507`)，然后在第 1873 行通过单独的 `ChangeSessionRepository` 查询重新填充 —— 这是 **DTO 断层**，但不影响前端（前端会叠加查询）

---

## 三、跨页面对比

| 数据域 | 仓库页 | 交付物页 | 审批页 | 治理页 | 项目总览 |
|---|---|---|---|---|---|
| 仓库绑定 | ✅ | — | — | — | ✅ |
| 快照 | ✅ | — | — | — | ✅ |
| 变更计划 | ✅ | — | — | — | ✅ |
| 变更批次 | ✅ | — | — | — | ✅ |
| 验证基线 | ✅ | — | — | — | — |
| 验证运行 | ✅ | — | — | — | — |
| 差异/证据 | ✅ | 🟡 | 🟡 | — | ✅ |
| 提交候选 | ✅ | — | — | — | ✅ |
| 文件定位 | ✅ | — | — | — | — |
| 上下文包 | ✅ | — | — | — | — |
| 发布门 | ✅ | — | ✅ | — | ✅ |
| 交付件列表 | — | 🔴 | — | — | — |
| 审批列表 | — | — | 🔴 | — | — |
| 角色目录 | — | — | — | ✅ | — |
| 技能注册 | — | — | — | ✅ | — |
| 记忆快照 | — | — | — | 🟡 | — |
| 治理巡检 | — | — | — | 🟡 | — |
| 项目列表 | — | — | — | — | ✅ |

图例: ✅ 已闭环 | 🟡 依赖上游或空态合理 | 🔴 接口存在但无数据 | — 不适用

---

## 四、按优先级推荐修复顺序

### P0 — 缺写入链路，前端空列表

| 序号 | 缺口 | 影响页面 | 最小修复建议 | 验收方式 |
|---|---|---|---|---|
| 1 | 交付件无自动生成 | 交付物页 | `task_worker.py` 的 `_finalize_execution()` 中，对 `provider_openai` 模式下成功的 run 自动调用 `DeliverableService.create_deliverable()` 创建交付件快照 | `GET /deliverables/projects/{pid}` 返回非空列表 |
| 2 | 审批无自动生成 | 审批页 | 优先等 P0-1 完成。在 release gate approve 或 commit candidate 创建成功后，自动调用 `ApprovalService.request_deliverable_approval()` 创建审批记录 | `GET /approvals/projects/{pid}` 返回非空列表 |

### P1 — DTO 断层 / 数据不完整

| 序号 | 缺口 | 影响页面 | 最小修复建议 | 验收方式 |
|---|---|---|---|---|
| 3 | `current_change_session` 硬编码 None | 项目详情 DTO | 移除 `projects.py:507` 的 `current_change_session=None`，改为直接查询 | `GET /projects/{pid}` 直接包含 change_session |
| 4 | 变更证据跨域组合无数据 | 仓库页差异面板 | 确保 change_batches + verification_runs 都生成后再查询 evidence | `GET /deliverables/projects/{pid}/change-evidence` 有内容 |
| 5 | 角色工作台 handoff 依赖日志文件 | 治理页角色工作台 | 把手 handoff 事件从日志文件迁移到 `run_handoffs` 或 `run_events` 表 | 不依赖磁盘日志文件 |

### P2 — 性能 / 健壮性

| 序号 | 缺口 | 影响范围 | 最小修复建议 |
|---|---|---|---|
| 6 | 项目总览每 5s 全表扫描 | CPU / 延迟 | 增加服务端缓存层或降低轮询频率 |
| 7 | 记忆快照每次刷新全量 5+ 表查询 | 治理页记忆模块 | 增量更新或增加刷新间隔 |
| 8 | 治理巡检点依赖 worker 才能初始化 | 治理页空态 | 项目创建时自动初始化空的 governance state 文件 |

---

## 五、已经过验证的真实闭环（不在本审计范围内）

以下已在之前的 smoke 和 E2E 测试中验证，**不需要重新审计**:

- **worker / provider / token accounting**: `smoke_live_provider_connectivity.py`, `smoke_plane_star_wars_single_runtime_closure.py`
- **release gate / apply-local / git-commit**: `smoke_backend_real_e2e_plane_star_wars.py`
- **task creation / run execution**: `POST /tasks`, `POST /workers/run-once`
- **project creation / planning**: `POST /planning/drafts`, `POST /planning/apply`

---

## 六、审计方法

### 仓库搜索命令和命中摘要

```bash
# 交付件自动生成检查
rg "DeliverableService" runtime/orchestrator/app/ --no-heading | head -30
# 命中: deliverable_service.py (definition), deliverables.py (routes), project_memory_service.py (memory refresh only)
# 未命中: task_worker.py, executor_service.py, project_stage_service.py
# 结论: 无 worker/executor 自动调用

# 审批自动生成检查
rg "ApprovalService" runtime/orchestrator/app/ --no-heading | head -20
# 命中: approval_service.py (definition), approvals.py (routes)
# 未命中: task_worker.py, executor_service.py, release gate flow
# 结论: 无 worker/executor 自动调用

# 项目总览 DTO 断层检查
rg "current_change_session=None" runtime/orchestrator/app/api/routes/projects.py
# 命中: line 507
# 结论: ProjectDetailResponse 构造时硬编码 None，需单独查询

# 仓库页数据链完整验证
rg "def list_project_change_batches|def list_project_commit_candidates|def get_project_day15_flow|def get_project_file_locator|def build_project_code_context_pack" runtime/orchestrator/app/api/routes/repositories.py --no-heading
# 命中: 全部 5 个端点均存在，且均使用 project_id 路径参数

# 治理记忆数据源检查
rg "def _refresh_project_memory" runtime/orchestrator/app/services/project_memory_service.py
# 确认: 从 5 个 repository 刷新（projects, tasks, runs, deliverables, approvals）

# 前端 hooks 覆盖检查
rg "export function use" apps/web/src/features/projects/hooks.ts apps/web/src/features/deliverables/hooks.ts apps/web/src/features/approvals/hooks.ts apps/web/src/features/roles/hooks.ts apps/web/src/features/skills/hooks.ts --no-heading
# 命中: 50+ 前端 hook，已全部追踪到对应后端路由
```

---

## 七、结论

**本阶段没有改前端、没有改后端、没有改 API 路径。**

审计覆盖了 5 个主要页面区域、20+ 个后端 API 端点、50+ 个前端 hook，形成了完整的缺口台账。

**第一批建议真正实现的 P0 后端缺口:**
1. 交付件自动生成 — 在 worker run 成功后自动创建交付件
2. 审批自动生成 — 在 release gate 或 commit candidate 流程中自动创建审批

这两个缺口修复后，交付物页和审批页将从始终空列表变为真实项目数据。

---

*台账由 Claude Code 审计生成 · 基于只读代码追踪 · 未修改任何源文件*
