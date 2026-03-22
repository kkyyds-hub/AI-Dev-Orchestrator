# Day08 角色工作台与协作可视化 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/02-模块B-角色化分工与SOP链路/01-计划文档/Day08-角色工作台与协作可视化.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 前端能按角色分栏展示当前任务与阻塞项
2. 角色之间的交接事件能实时展示
3. 用户可以从角色视图跳转到任务、运行和项目详情
4. 角色工作台与老板首页共享一套核心数据口径
5. 最小烟测能验证角色视图与 SSE 更新链路

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `apps/web/src/features/roles/RoleWorkbenchPage.tsx`
3.    - `apps/web/src/features/roles/components/RoleLaneBoard.tsx`
4.    - `apps/web/src/features/roles/components/HandoffTimeline.tsx`
5.    - `runtime/orchestrator/app/api/routes/console.py`
6.    - `runtime/orchestrator/app/services/console_service.py`
7.    - `runtime/orchestrator/app/services/event_stream_service.py`

8. 检查后端路由、服务或 Worker 链路是否已接通。
9. 检查前端页面、侧板或时间线是否能展示对应信息。
10. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已完成 Day08 范围内的角色工作台、交接时间线、任务 / 运行 / 项目跳转入口，以及 `role_handoff` SSE 更新链路，并通过最小烟测与前后端构建验证。
- 证据：
1. `D:\AI-Dev-Orchestrator\runtime\orchestrator\.venv\Scripts\python.exe -X utf8 scripts/v3b_day08_role_workbench_smoke.py`：通过；验证了 `/console/role-workbench` 返回的角色列聚合结果，以及 `role_handoff` SSE 事件能携带项目 / 任务 / 运行上下文。
2. `python -X utf8 -m compileall app`（工作目录：`runtime/orchestrator`）：通过；覆盖 Day08 改动后的后端源码编译检查。
3. `npm.cmd run build`（工作目录：`apps/web`）：通过；覆盖角色工作台页面、交接时间线与跳转联动的前端类型和构建验证。

---

## 后续补测建议

1. 先完成对应计划文档中的关键产物，再按本文件逐项补测。
2. 若状态进入“进行中”，补齐缺口说明，不要直接标记为“通过”。
3. 若状态进入“已完成”，补结构化证据、最小烟测结果和必要的回归说明。
