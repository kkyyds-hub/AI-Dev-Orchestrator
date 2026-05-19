# /execution?tab=tasks 任务操作闭环验收记录 (Phase 2)

> 验收日期：2026-05-19
> 验收范围：TASK-06 ~ TASK-10
> 基线提交：376e340 → (本次)
> 验收方法：代码审查 + 功能补齐 + build 验证
> 配套文档：closure-checklist-20260518.md

---

## 操作入口

所有任务操作按钮位于 **TaskDetailDrawer**（抽屉），不常驻任务行。

代码位置：
- 抽屉：`apps/web/src/pages/tasks/components/TaskDetailDrawer.tsx`
- 操作按钮渲染：TaskDetailDrawer.tsx:182-230

## 验收结果

| ID | 验收项 | 通过标准 | 状态 | 证据 |
|---|---|---|---|---|
| TASK-06 | 暂停是否真实调用后端 | 状态改变 | Pass | 前端入口: TaskDetailDrawer "暂停"按钮 → `onPause(taskId)` → `usePauseTask().mutate(taskId)` → POST `/tasks/:id/pause`。按钮条件: running/pending/blocked 时可见。 |
| TASK-07 | 恢复是否真实调用后端 | 状态改变 | Pass | 前端入口: TaskDetailDrawer "恢复"按钮 → `onResume(taskId)` → `useResumeTask().mutate(taskId)` → POST `/tasks/:id/resume`。按钮条件: paused 时可见。 |
| TASK-08 | 请求人工是否真实调用后端 | waiting_human 状态 | Pass | 前端入口: TaskDetailDrawer "请求人工"按钮 → `onRequestHuman(taskId)` → `useRequestHumanReview().mutate(taskId)` → POST `/tasks/:id/request-human`。按钮条件: 非 waiting_human 状态可见。 |
| TASK-09 | 人工已处理是否真实调用后端 | 状态回到可调度 | Pass | 前端入口: TaskDetailDrawer "人工已处理"按钮 → `onResolveHuman(taskId)` → `useResolveHumanReview().mutate(taskId)` → POST `/tasks/:id/resolve-human`。按钮条件: waiting_human 状态可见。 |
| TASK-10 | 重新入队文案是否准确 | 说明"下一次调度执行"，不等于立即运行 | Pass | 前端入口: TaskDetailDrawer "重新入队"按钮 → `onRetry(taskId)` → `useRetryTask().mutate(taskId)` → POST `/tasks/:id/retry`。按钮下方文案: "重置为待执行，下一次 Worker 调度时执行"。按钮条件: failed/blocked 时可见。 |

## API 真实闭环

| 操作 | 前端入口 | hooks.ts | api.ts | HTTP |
|---|---|---|---|---|
| 暂停 | TaskDetailDrawer:191 | usePauseTask:85 | pauseTask:28 | POST /tasks/:id/pause |
| 恢复 | TaskDetailDrawer:198 | useResumeTask:99 | resumeTask:38 | POST /tasks/:id/resume |
| 请求人工 | TaskDetailDrawer:205 | useRequestHumanReview:103 | requestHumanReview:44 | POST /tasks/:id/request-human |
| 人工已处理 | TaskDetailDrawer:212 | useResolveHumanReview:107 | resolveHumanReview:52 | POST /tasks/:id/resolve-human |
| 重新入队 | TaskDetailDrawer:219 | useRetryTask:51 | retryTask:22 | POST /tasks/:id/retry |

## 数据刷新

所有 mutation 的 onSuccess 回调均调用 `queryClient.invalidateQueries` 刷新 console-overview 和 task-detail 等查询缓存，操作后任务列表和抽屉数据会自动更新。

## 按钮状态控制 (已对齐后端 TaskStateMachineService)

| 按钮 | 前端可见条件 | 后端 allowed_statuses | 来源 |
|---|---|---|---|
| 暂停 | pending / failed / blocked | PENDING, FAILED, BLOCKED | build_pause_transition:115 |
| 恢复 | paused | PAUSED | build_resume_transition:134 |
| 请求人工 | pending / failed / blocked / paused | PENDING, FAILED, BLOCKED, PAUSED | build_request_human_review_transition:159-163 |
| 人工已处理 | waiting_human | WAITING_HUMAN | build_resolve_human_review_transition:191 |
| 重新入队 | failed / blocked | FAILED, BLOCKED | build_retry_transition:95 |

前端状态条件已严格对齐后端 TaskStateMachineService 的 `_ensure_allowed` 检查。
running / completed 状态下所有操作按钮均隐去，避免前端显示后点击即 409。

操作中 (isPending) 时按钮显示处理中状态并 disabled，操作失败时按钮变红并显示错误信息。

## Gate 结论

**Pass** — 全部 5 项操作闭环验收通过。前端按钮可见条件已对齐后端状态机，所有按钮调用真实 POST API，操作后数据自动刷新，重新入队文案准确。
