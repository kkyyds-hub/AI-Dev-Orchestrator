# Day03 项目级规划入口与任务映射

- 版本：`V3`
- 模块 / 提案：`模块A：项目级编排与老板入口`
- 原始日期：`2026-04-08`
- 原始来源：`V3 正式版总纲 / 模块A：项目级编排与老板入口 / Day03`
- 当前回填状态：**已完成**
- 回填口径：已按 Day03 范围完成项目级规划入口、项目草案应用与任务映射，并补充最小烟测验证。

---

## 今日目标

让一个项目 brief 不再只生成散落任务，而是先形成项目，再把草案映射为项目内任务。

---

## 当日交付

1. `runtime/orchestrator/app/services/planner_service.py`
2. `runtime/orchestrator/app/services/project_service.py`
3. `runtime/orchestrator/app/api/routes/planning.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectCreateFlow.tsx`
6. `apps/web/src/features/projects/components/ProjectDraftPanel.tsx`

---

## 验收点

1. 用户可以从 brief 创建项目草案与项目摘要
2. 项目草案应用后，生成的任务自动挂到目标项目下
3. 项目详情能看见任务树和草案来源
4. 项目创建链路保留人工调整空间，不强制一键自动执行
5. 现有 `planning/drafts` 与 `planning/apply` 能平滑兼容项目模式


---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已把现有 `planning/drafts` / `planning/apply` 平滑升级为项目模式兼容入口：草案阶段补充 `project` 草案，应用阶段支持“创建项目并映射任务”，项目详情页可读取任务树与草案来源，且整条链路仍保留人工调整空间，不会自动触发执行。
- 回填证据：
1. `runtime/orchestrator/app/services/planner_service.py` 已新增 `PlannedProjectDraft`，并在 `apply_plan_draft()` 中支持创建项目、映射任务与保留 `source_draft_id`
2. `runtime/orchestrator/app/services/project_service.py`、`runtime/orchestrator/app/repositories/task_repository.py` 与 `runtime/orchestrator/app/api/routes/projects.py` 已补齐项目详情任务树数据
3. `runtime/orchestrator/app/domain/task.py`、`runtime/orchestrator/app/core/db_tables.py`、`runtime/orchestrator/app/core/db.py` 已补齐 `tasks.source_draft_id` 增量字段
4. `runtime/orchestrator/app/api/routes/planning.py` 已兼容项目草案入参/出参，同时保留旧 `planning/drafts` / `planning/apply` 调用方式
5. `apps/web/src/features/projects/ProjectCreateFlow.tsx` 与 `apps/web/src/features/projects/components/ProjectDraftPanel.tsx` 已落地 Day03 的项目级规划入口、草案编辑与应用按钮
6. `apps/web/src/features/projects/ProjectOverviewPage.tsx` 已在项目详情区域补充任务树与草案来源展示
7. `runtime/orchestrator/scripts/v3a_day03_project_planning_smoke.py` 已完成最小烟测，验证项目模式与旧兼容模式同时可用

---

## 关键产物路径

1. `runtime/orchestrator/app/services/planner_service.py`
2. `runtime/orchestrator/app/services/project_service.py`
3. `runtime/orchestrator/app/api/routes/planning.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectCreateFlow.tsx`
6. `apps/web/src/features/projects/components/ProjectDraftPanel.tsx`


---

## 上下游衔接

- 前一日：Day02 老板首页与项目总览看板
- 后一日：Day04 项目里程碑与阶段守卫
- 对应测试文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/02-测试验证/Day03-项目级规划入口与任务映射-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；若当日未完成，则顺延到下一日并同步更新模块状态与测试文档。

### 备注
1. Day03 把你现有 Planner 从“任务草案器”升级为“项目规划入口”。
