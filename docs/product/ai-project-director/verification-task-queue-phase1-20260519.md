# /execution?tab=tasks 任务队列第一阶段验收记录

> 验收日期：2026-05-19
> 验收范围：TASK-01, TASK-03, TASK-05, TASK-11, TASK-12
> 基线提交：3319c3e
> 验收方法：代码审查 + build 验证
> 配套文档：closure-checklist-20260518.md

---

## 验收结果

| ID | 验收项 | 通过标准 | 状态 | 证据 | 备注 |
|---|---|---|---|---|---|
| TASK-01 | 任务是否按调度优先级分组 | 待人工/阻塞、执行中、可调度、等待依赖、已完成 | **Pass** | `TaskQueueList.tsx:19-51` — groupTasks() 五组分类：1) 待人工/阻塞/失败 2) 执行中 3) 可调度/待执行 4) 等待依赖/暂停 5) 已完成 | failed 归入 critical 组，不进入 completed 折叠组。空组不显示。 |
| TASK-03 | 每个任务是否只展示核心 6 项 | 标题、状态、Agent、优先级、阻塞/依赖、最近运行 | **Pass** | `TaskQueueList.tsx:210-291` — TaskQueueItem 渲染 3 行：1) 标题+状态+优先级 2) Agent+依赖+阻塞原因 3) 运行摘要+操作按钮 | 无长 ID、成本、input_summary。 |
| TASK-05 | 任务详情是否用抽屉 | 不做常驻大右栏 | **Pass** | `ExecutionTasksTab.tsx:274-281` — `<TaskDetailDrawer>` 仅在 selectedTask 非 null 时渲染。TaskDetailPanel 未导入，不在首屏常驻。 | 抽屉：固定定位右侧面板+遮罩，点击任务行或 URL 含 taskId 触发。 |
| TASK-11 | 查看运行是否跳运行观测 | 带 runId/taskId | **Pass** | `ExecutionTasksTab.tsx:108-114` — handleNavigateToRun 使用 buildRunRoute({runId, taskId, projectId}) 生成 /runs/:runId?taskId=xxx&projectId=xxx。无 latest_run 时按钮 disabled（title="无最近运行"）。 | |
| TASK-12 | 查看仓库上下文是否跳仓库工作区 | 带 taskId/projectId | **Pass** | `ExecutionTasksTab.tsx:117-125` — handleNavigateToRepository 跳 /projects/:pid/repository?taskId=xxx。无 project_id 时按钮 disabled（title="缺少项目上下文"）。 | |

---

## 附加验证

| 项目 | 状态 |
|---|---|
| 已完成组默认折叠 | Pass — `TaskQueueList.tsx:48` collapsible=true, line 110 useState(collapsedByDefault) |
| 工作区固定高度 | Pass — `ExecutionTasksTab.tsx:235-236` height: calc(100vh - 260px) |
| 左侧内部滚动 | Pass — `ExecutionTasksTab.tsx:238` overflow-y-auto |
| 右侧 sticky | Pass — `ExecutionTasksTab.tsx:250` sticky top-0 |
| /tasks 重定向 | Pass — TasksPage.tsx 使用 `<Navigate to="/execution?tab=tasks">` |
| 侧边栏收敛 | Pass — 无"任务""运行观测"入口 |
| build 通过 | Pass — tsc -b && vite build ✓ |

---

## Gate 结论

**Pass**

全部 5 项 TASK 验收通过，无代码缺陷。failed 正确归入"待人工/阻塞/失败"组；优先级恢复展示；分组顺序、核心字段、抽屉、运行跳转、仓库跳转均符合文档要求。
