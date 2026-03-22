# Day04 项目里程碑与阶段守卫

- 版本：`V3`
- 模块 / 提案：`模块A：项目级编排与老板入口`
- 原始日期：`2026-04-09`
- 原始来源：`V3 正式版总纲 / 模块A：项目级编排与老板入口 / Day04`
- 当前回填状态：**已完成**
- 回填口径：已按 Day04 范围完成项目里程碑、阶段守卫、阶段推进时间线与最小前后端闭环，并补充 Day04 烟测验证。

---

## 今日目标

为项目补齐里程碑、阶段守卫和阶段推进规则，让项目不会在没有准备好的情况下盲目前进。

---

## 当日交付

1. `runtime/orchestrator/app/services/task_state_machine_service.py`
2. `runtime/orchestrator/app/services/project_stage_service.py`
3. `runtime/orchestrator/app/services/task_readiness_service.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectMilestonePanel.tsx`
6. `apps/web/src/features/projects/ProjectStageTimeline.tsx`

---

## 验收点

1. 项目阶段拥有明确状态与合法转移规则
2. 里程碑未满足时，项目不能进入下一阶段
3. 项目详情页能展示里程碑完成情况和阻塞原因
4. 阶段守卫与现有任务守卫口径保持一致
5. 阶段推进动作可审计、可回放


---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 `ProjectStageService`，为项目建立线性阶段推进规则、阶段时间线与里程碑守卫；项目详情接口已补充阶段守卫、里程碑与阶段审计记录；前端项目详情页已新增里程碑面板与阶段时间线组件，并支持“推进成功 / 守卫拦截”两类动作回放。
- 回填证据：
1. `runtime/orchestrator/app/domain/project.py` 已新增 `ProjectMilestone / ProjectStageGuard / ProjectStageHistoryEntry / ProjectStageBlockingTask`
2. `runtime/orchestrator/app/services/project_stage_service.py` 已完成阶段推进规则、里程碑检查、阻塞任务归因与阶段审计写入
3. `runtime/orchestrator/app/services/task_readiness_service.py` 与 `runtime/orchestrator/app/services/task_state_machine_service.py` 已补齐项目阶段守卫复用的任务就绪/状态口径
4. `runtime/orchestrator/app/repositories/project_repository.py`、`runtime/orchestrator/app/core/db_tables.py` 与 `runtime/orchestrator/app/core/db.py` 已补齐 `projects.stage_history_json` 持久化与增量迁移
5. `runtime/orchestrator/app/api/routes/projects.py` 已补齐项目详情 `stage_guard / stage_timeline` 字段与 `POST /projects/{project_id}/advance-stage`
6. `apps/web/src/features/projects/ProjectOverviewPage.tsx`、`ProjectMilestonePanel.tsx` 与 `ProjectStageTimeline.tsx` 已落地项目里程碑展示、阶段推进按钮与时间线回放
7. `runtime/orchestrator/scripts/v3a_day04_project_stage_guard_smoke.py` 已完成最小烟测，覆盖里程碑未满足拦截、阶段推进成功、阻塞原因展示与时间线审计

---

## 关键产物路径

1. `runtime/orchestrator/app/services/task_state_machine_service.py`
2. `runtime/orchestrator/app/services/project_stage_service.py`
3. `runtime/orchestrator/app/services/task_readiness_service.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectMilestonePanel.tsx`
6. `apps/web/src/features/projects/ProjectStageTimeline.tsx`


---

## 上下游衔接

- 前一日：Day03 项目级规划入口与任务映射
- 后一日：Day05 角色目录与身份配置模型
- 对应测试文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/02-测试验证/Day04-项目里程碑与阶段守卫-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；若当日未完成，则顺延到下一日并同步更新模块状态与测试文档。

### 备注
1. Day04 收口模块A，让后续角色化和审批流都建立在项目阶段之上。
2. 本次只实现 Day04 的项目里程碑与阶段守卫，不扩展到 Day05 角色目录、SOP 模板或审批系统。
