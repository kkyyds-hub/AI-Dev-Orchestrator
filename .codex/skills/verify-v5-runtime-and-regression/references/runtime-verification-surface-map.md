# V5 运行验证表面图

## 1. 目的

把 `verify-v5-runtime-and-regression` 绑定到仓库里真实存在的验证入口，避免线程一上来就空谈“应该能跑”。

这个参考文件回答六个问题：

1. 当前后端和前端各有哪些稳定验证入口
2. 哪些地方适合做最小冒烟
3. 哪些地方可以提供结构化证据
4. 前端结构治理后应该优先看哪些入口
5. 测试锚点变更后应该优先看哪些脚本和页面
6. 一个验证线程通常应先从哪里下手

## 2. 当前已确认的后端验证入口

### 启动与应用入口

- `runtime/orchestrator/README.md`
- `runtime/orchestrator/app/main.py`
- `runtime/orchestrator/app/api/routes/health.py`

当前已确认：

- README 已给出稳定的本地运行方式。
- `health` 路由可作为最小启动与服务可用性检查入口。

### worker / runs / events 观察面

- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/api/routes/events.py`
- `runtime/orchestrator/app/workers/task_worker.py`

当前已确认：

- `workers` 可用于显式触发一次 worker 或 worker pool。
- `runs` 可读取运行日志与验证结果相关信息。
- `events` 可提供实时事件流观察面。
- `task_worker.py` 是判断执行主链是否真的走通的核心入口。

### 验证与日志服务

- `runtime/orchestrator/app/services/verifier_service.py`
- `runtime/orchestrator/app/services/run_logging_service.py`

当前已确认：

- `VerifierService` 已支持模板化最小验证。
- `RunLoggingService` 能把运行过程写入本地 JSONL，适合作为强证据来源。

### 现有 smoke 脚本

- `runtime/orchestrator/scripts/*_smoke.py`
- 例如：
  - `runtime/orchestrator/scripts/v5_day07_control_surface_degraded_smoke.py`
  - `runtime/orchestrator/scripts/v5_day07_minimal_continuous_regression_pack.py`

当前已确认：

- 仓库已经有大量分阶段 smoke 脚本。
- 新线程做验证时，优先复用现有脚本，而不是凭空发明新的验证入口。
- 涉及 V5 控制面或连续回归时，可优先查看 V5 day07 相关脚本是否贴近当前场景。

## 3. 当前已确认的前端验证入口

### 前端构建入口

- `apps/web/package.json`

当前已确认：

- 前端存在稳定的 `npm run build` 构建入口。
- 当前 `package.json` 默认暴露的是 `dev` / `build` / `preview`，不要假定存在统一测试命令。
- 前端最小事实确认通常先从 `npm run build` 开始。

### 前端应用入口

- `apps/web/src/app/App.tsx`
- `apps/web/src/app/main.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`

当前已确认：

- 这里是当前 Web 应用入口与聚合页入口。
- 页面级验证通常要从这里确认导航、挂载与顶层依赖关系。
- 结构治理后的联调影响确认，优先回看这些入口是否仍稳定。

### V5 控制面基础页面

- `apps/web/src/features/approvals/`
- `apps/web/src/features/budget/`
- `apps/web/src/features/console/`
- `apps/web/src/features/console-metrics/`
- `apps/web/src/features/deliverables/`
- `apps/web/src/features/events/`
- `apps/web/src/features/projects/`
- `apps/web/src/features/repositories/`
- `apps/web/src/features/roles/`
- `apps/web/src/features/run-log/`
- `apps/web/src/features/skills/`
- `apps/web/src/features/strategy/`
- `apps/web/src/features/task-actions/`
- `apps/web/src/features/task-detail/`

当前已确认：

- 这些 feature 已经形成了 V5 控制面与观察面的主要入口。
- 验证前端时，优先验证与当前改动直接相关的 feature，而不是一上来全扫。

## 4. 前端结构治理与锚点同步的观察面

### 结构治理优先观察面

- `apps/web/src/app/App.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- 本轮被拆出的 `sections/*`、`panel/*`、`hooks.ts`、`types.ts`、`api.ts`

当前已确认：

- 入口页与聚合页是结构治理最容易引发联调回归的地方。
- 结构治理后的 verify，不是继续讨论“怎么拆”，而是确认“拆完之后入口和旧链路有没有明显坏”。

### 锚点与脚本优先观察面

- 源码中的 `data-testid`
- `apps/web/scripts/day07_manual_run_card_evidence.spec.mjs`
- `apps/web/scripts/day07_negative_sample_page_consistency.spec.mjs`
- `apps/web/scripts/day07_same_sample_page_consistency.spec.mjs`

当前已确认：

- 仓库里已存在脚本级页面一致性与证据脚本。
- 锚点变更后的 verify，应该优先看受影响 `data-testid` 与这些脚本之间是否仍对齐。
- 如果没实际跑脚本，也要把“仅做代码核对”写清楚。

## 5. 推荐验证顺序

建议顺序：

1. 先确认本次声称已完成的是什么，以及来自哪个上游 skill
2. 选最小验证入口
3. 先做 build / 启动 / API / script 这种强证据层
4. 再补页面、联调或锚点同步验证
5. 最后再写分级结论与下一棒建议

如果还没选定验证入口，就不要先写“通过”结论。
