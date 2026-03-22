# Day03 项目级规划入口与任务映射 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/01-计划文档/Day03-项目级规划入口与任务映射.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 用户可以从 brief 创建项目草案与项目摘要
2. 项目草案应用后，生成的任务自动挂到目标项目下
3. 项目详情能看见任务树和草案来源
4. 项目创建链路保留人工调整空间，不强制一键自动执行
5. 现有 `planning/drafts` 与 `planning/apply` 能平滑兼容项目模式


---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/planner_service.py`
3.    - `runtime/orchestrator/app/services/project_service.py`
4.    - `runtime/orchestrator/app/api/routes/planning.py`
5.    - `runtime/orchestrator/app/api/routes/projects.py`
6.    - `apps/web/src/features/projects/ProjectCreateFlow.tsx`
7.    - `apps/web/src/features/projects/components/ProjectDraftPanel.tsx`

8. 检查后端路由、服务或 Worker 链路是否已接通。
9. 检查前端页面、侧板或时间线是否能展示对应信息。
10. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已完成项目级规划入口、项目草案应用与任务映射实现，并通过 Day03 最小烟测、Day01/Day02 回归烟测与前端构建验证。
- 证据：
1. 运行 `runtime/orchestrator/scripts/v3a_day03_project_planning_smoke.py`，验证从 brief 生成项目草案、应用后任务自动挂到项目下、项目详情返回任务树与 `source_draft_id`、旧兼容模式仍可创建未挂项目任务
2. 运行 `runtime/orchestrator/scripts/v3a_day01_project_smoke.py`，确认新增 `source_draft_id` 列后 Day01 的项目建模与任务挂载能力仍正常
3. 运行 `runtime/orchestrator/scripts/v3a_day02_boss_home_smoke.py`，确认老板首页总览与旧 `/tasks/console` 能力仍共存
4. 在 `apps/web` 执行 `npm run build`，确认 `ProjectCreateFlow.tsx`、`ProjectDraftPanel.tsx` 与项目详情树展示通过 TypeScript/Vite 构建

---

## 后续补测建议

1. 先完成对应计划文档中的关键产物，再按本文件逐项补测。
2. 若状态进入“进行中”，补齐缺口说明，不要直接标记为“通过”。
3. 若状态进入“已完成”，补结构化证据、最小烟测结果和必要的回归说明。
