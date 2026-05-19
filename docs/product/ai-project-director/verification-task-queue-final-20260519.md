# /execution?tab=tasks 任务队列阶段最终收口验收

> 验收日期：2026-05-19
> 基线提交：2960e0c
> 验收范围：TASK-01 ~ TASK-14（全量）
> 验收方法：静态代码审查 + build 验证
> 评判依据：closure-checklist-20260518.md / page-information-architecture-20260518.md / closure-flow-20260518.md

---

## 验收结论总表

| ID | 验收项 | 状态 | 代码证据 | 备注 |
|---|---|---|---|---|
| TASK-01 | 任务按调度优先级分组 | **Pass** | TaskQueueList.tsx:19-51 | 五组：待人工/阻塞/失败→执行中→可调度/待执行→等待依赖/暂停→已完成（折叠） |
| TASK-02 | 任务列表弱化表格感 | **Pass** | TaskQueueList.tsx:202-208 | 无 HTML table，bordered card div 轻列表 |
| TASK-03 | 每个任务只展示核心 6 项 | **Pass** | TaskQueueList.tsx:210-291 | 标题、状态、Agent(owner_role_code)、优先级(priority)、阻塞/依赖、最近运行摘要。无长 ID/成本。 |
| TASK-04 | 右侧为执行态势面板 | **Pass** | TaskExecutionSituationPanel.tsx | Agent 负载（含执行中/阻塞明细）、阻塞原因(≤3)、最近运行(≤3 可点击)、规则建议 |
| TASK-05 | 任务详情用抽屉 | **Pass** | ExecutionTasksTab.tsx:325-341 | TaskDetailDrawer 固定定位右侧面板+遮罩，条件渲染；TaskDetailPanel 未导入 |
| TASK-06 | 暂停真实调用后端 | **Pass** | TaskDetailDrawer.tsx:195-202 | pending/failed/blocked → POST /tasks/:id/pause；对齐 build_pause_transition:115 |
| TASK-07 | 恢复真实调用后端 | **Pass** | TaskDetailDrawer.tsx:203-209 | paused → POST /tasks/:id/resume；对齐 build_resume_transition:134 |
| TASK-08 | 请求人工真实调用后端 | **Pass** | TaskDetailDrawer.tsx:211-217 | pending/failed/blocked/paused → POST /tasks/:id/request-human；对齐 build_request_human_review_transition:159-163 |
| TASK-09 | 人工已处理真实调用后端 | **Pass** | TaskDetailDrawer.tsx:219-225 | waiting_human → POST /tasks/:id/resolve-human；对齐 build_resolve_human_review_transition:191 |
| TASK-10 | 重新入队文案准确 | **Pass** | TaskDetailDrawer.tsx:235-236 | "重置为待执行，下一次 Worker 调度时执行"；failed/blocked → POST /tasks/:id/retry |
| TASK-11 | 查看运行跳运行观测 | **Pass** | ExecutionTasksTab.tsx:117-128 | buildRunRoute({runId, taskId, projectId}) → /runs/:runId?taskId=xxx&projectId=xxx |
| TASK-12 | 查看仓库上下文跳仓库工作区 | **Pass** | ExecutionTasksTab.tsx:131-138 | /projects/:pid/repository?taskId=xxx；无 project_id 时 disabled |
| TASK-13 | 不展示完整日志 | **Pass** | 全量代码审查 | 无完整日志渲染；日志去运行观测 |
| TASK-14 | 不展示完整仓库树 | **Pass** | 全量代码审查 | 无仓库树渲染；仓库树去仓库弹窗 |

## 跨领域验证

| 检查项 | 状态 | 证据 |
|---|---|---|
| /execution?tab=tasks 页面职责是任务队列，不越界 | Pass | ExecutionCenterPage.tsx:117 渲染 ExecutionTasksTab，仅为任务队列 |
| /tasks 重定向到 /execution?tab=tasks | Pass | TasksPage.tsx:17 `<Navigate to="/execution?..." replace />` 保留 projectId/taskId |
| 侧边栏无"任务""运行观测" | Pass | navigation.ts:15-52 PRIMARY_NAV_ITEMS 仅含"执行中心" |
| failed 在"待人工/阻塞/失败"组 | Pass | TaskQueueList.tsx:27 critical.push(t) for failed |
| priority 常驻展示 | Pass | TaskQueueList.tsx:216-218 prioLabel 渲染 P0-P3/高/中/低 |
| 状态操作仅在抽屉内 | Pass | TaskDetailDrawer.tsx:193-239 操作按钮，不放任务行 |
| 所有操作调用真实 API + 数据刷新 | Pass | hooks.ts onSuccess → invalidateQueries |
| 不展示完整运行日志/仓库树/交付物/审批 | Pass | 全量审查 |
| 无 TaskTableSection 恢复 | Pass | 未导入 TaskTableSection |
| 无 TaskDetailPanel 常驻 | Pass | 未导入 TaskDetailPanel |
| 无长说明文案 | Pass | 全量审查 |
| /runs/仓库页/运行观测/仓库工作区页签未改动 | Pass | 未修改相关文件 |
| build | Pass | tsc -b && vite build ✓ |

## 风险与遗留

| 风险 | 级别 | 说明 |
|---|---|---|
| /runs 页签仍是占位跳转 | 低 | 预留后续阶段接入，不影响任务队列闭环 |

## Gate 结论

**Pass** — TASK-01~TASK-14 全部通过。无未闭环项，无回归缺陷。任务队列阶段可从 Partial 收口为 Pass。
