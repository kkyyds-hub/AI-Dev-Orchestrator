# Day08 角色工作台与协作可视化

- 版本：`V3`
- 模块 / 提案：`模块B：角色化分工与SOP链路`
- 原始日期：`2026-04-13`
- 原始来源：`V3 正式版总纲 / 模块B：角色化分工与SOP链路 / Day08`
- 当前回填状态：**已完成**
- 回填口径：已完成角色工作台页面、角色分栏聚合接口、交接时间线与 SSE 驱动的协作可视化联动。

---

## 今日目标

把角色链路展示到前端，让老板能直观看到 PM、架构师、工程师、评审者各自在做什么。

---

## 当日交付

1. `apps/web/src/features/roles/RoleWorkbenchPage.tsx`
2. `apps/web/src/features/roles/components/RoleLaneBoard.tsx`
3. `apps/web/src/features/roles/components/HandoffTimeline.tsx`
4. `runtime/orchestrator/app/api/routes/console.py`
5. `runtime/orchestrator/app/services/console_service.py`
6. `runtime/orchestrator/app/services/event_stream_service.py`

---

## 验收点

1. 前端能按角色分栏展示当前任务与阻塞项
2. 角色之间的交接事件能实时展示
3. 用户可以从角色视图跳转到任务、运行和项目详情
4. 角色工作台与老板首页共享一套核心数据口径
5. 最小烟测能验证角色视图与 SSE 更新链路

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已在后端补齐 `/console/role-workbench` 聚合口径，前端新增正式的角色工作台页面、角色分栏看板、交接时间线与任务 / 运行 / 项目详情跳转入口，并通过 `role_handoff` SSE 事件驱动实时刷新。
- 回填证据：
1. `runtime/orchestrator/app/services/console_service.py`、`runtime/orchestrator/app/api/routes/console.py`：新增角色工作台聚合模型、角色列、任务卡片、交接时间线与 `/console/role-workbench` 接口。
2. `runtime/orchestrator/app/services/event_stream_service.py`、`runtime/orchestrator/app/services/run_logging_service.py`、`runtime/orchestrator/app/workers/task_worker.py`：新增 `role_handoff` SSE 事件发布链路，并把项目 / 任务 / 运行上下文带入交接事件。
3. `apps/web/src/features/roles/RoleWorkbenchPage.tsx`、`apps/web/src/features/roles/components/RoleLaneBoard.tsx`、`apps/web/src/features/roles/components/HandoffTimeline.tsx`、`apps/web/src/app/App.tsx`：新增角色工作台页面、角色分栏组件、交接时间线，以及到项目详情 / 任务详情 / 运行详情的联动跳转。
4. `runtime/orchestrator/scripts/v3b_day08_role_workbench_smoke.py`、`python -X utf8 -m compileall app`、`npm.cmd run build`：完成 Day08 最小烟测与前后端构建验证。

---

## 关键产物路径

1. `apps/web/src/features/roles/RoleWorkbenchPage.tsx`
2. `apps/web/src/features/roles/components/RoleLaneBoard.tsx`
3. `apps/web/src/features/roles/components/HandoffTimeline.tsx`
4. `runtime/orchestrator/app/api/routes/console.py`
5. `runtime/orchestrator/app/services/console_service.py`
6. `runtime/orchestrator/app/services/event_stream_service.py`

---

## 上下游衔接

- 前一日：Day07 角色任务分派与协作链路
- 后一日：Day09 交付件仓库与版本快照
- 对应测试文档：`docs/01-版本冻结计划/V3/02-模块B-角色化分工与SOP链路/02-测试验证/Day08-角色工作台与协作可视化-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无。

### 备注
1. Day08 完成后，V3 的“AI 软件公司工作台”首次具备正式的角色看板与协作状态可视化。
