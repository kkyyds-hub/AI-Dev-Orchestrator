# Day04 项目里程碑与阶段守卫 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/01-计划文档/Day04-项目里程碑与阶段守卫.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目阶段拥有明确状态与合法转移规则
2. 里程碑未满足时，项目不能进入下一阶段
3. 项目详情页能展示里程碑完成情况和阻塞原因
4. 阶段守卫与现有任务守卫口径保持一致
5. 阶段推进动作可审计、可回放


---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/task_state_machine_service.py`
3.    - `runtime/orchestrator/app/services/project_stage_service.py`
4.    - `runtime/orchestrator/app/services/task_readiness_service.py`
5.    - `runtime/orchestrator/app/api/routes/projects.py`
6.    - `apps/web/src/features/projects/ProjectMilestonePanel.tsx`
7.    - `apps/web/src/features/projects/ProjectStageTimeline.tsx`

8. 检查后端路由、服务或 Worker 链路是否已接通。
9. 检查前端页面、侧板或时间线是否能展示对应信息。
10. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已完成项目里程碑、阶段守卫、阶段推进时间线与前端详情展示，并通过 Day04 烟测、Day01-Day03 回归烟测与前端构建验证。
- 证据：
1. 运行 `runtime/orchestrator/scripts/v3a_day04_project_stage_guard_smoke.py`，验证阶段合法转移、里程碑未满足拦截、阻塞任务/阻塞原因展示、阶段推进审计写入与时间线回放
2. 运行 `runtime/orchestrator/scripts/v3a_day01_project_smoke.py`，确认新增 `projects.stage_history_json` 后 Day01 项目建模与旧库迁移链路仍正常
3. 运行 `runtime/orchestrator/scripts/v3a_day02_boss_home_smoke.py`，确认老板首页项目总览与旧任务控制台能力继续共存
4. 运行 `runtime/orchestrator/scripts/v3a_day03_project_planning_smoke.py`，确认 Day03 项目规划入口、任务映射与项目详情树数据未被 Day04 破坏
5. 在 `apps/web` 执行 `npm run build`，确认 `ProjectMilestonePanel.tsx`、`ProjectStageTimeline.tsx` 与 `ProjectOverviewPage.tsx` 通过 TypeScript/Vite 构建

---

## 后续补测建议

1. 先完成对应计划文档中的关键产物，再按本文件逐项补测。
2. 若状态进入“进行中”，补齐缺口说明，不要直接标记为“通过”。
3. 若状态进入“已完成”，补结构化证据、最小烟测结果和必要的回归说明。
