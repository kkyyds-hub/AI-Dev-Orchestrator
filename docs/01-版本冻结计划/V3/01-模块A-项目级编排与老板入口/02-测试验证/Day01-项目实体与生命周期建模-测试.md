# Day01 项目实体与生命周期建模 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/01-计划文档/Day01-项目实体与生命周期建模.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目可以被创建、查询、列表化读取
2. 项目拥有明确的状态、阶段、摘要和基础统计字段
3. 任务可以挂到项目下，项目能看到聚合任务数量与状态分布
4. 数据库完成最小增量升级，不破坏现有 `Task / Run` 数据
5. API 字段口径与领域模型保持一致


---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/project.py`
3.    - `runtime/orchestrator/app/repositories/project_repository.py`
4.    - `runtime/orchestrator/app/services/project_service.py`
5.    - `runtime/orchestrator/app/core/db_tables.py`
6.    - `runtime/orchestrator/app/core/db.py`
7.    - `runtime/orchestrator/app/api/routes/projects.py`

8. 检查后端路由、服务或 Worker 链路是否已接通。
9. 检查前端页面、侧板或时间线是否能展示对应信息。
10. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已按 Day01 范围完成实现，并完成最小编译校验与项目烟测验证。
- 证据：
1. 执行 `python -m compileall runtime/orchestrator/app runtime/orchestrator/scripts/v3a_day01_project_smoke.py`，新增代码通过编译检查
2. 在 `runtime/orchestrator` 目录执行 `python scripts/v3a_day01_project_smoke.py`，确认 `projects` 表创建成功且 `tasks.project_id` 已完成增量迁移
3. 烟测确认旧 `tasks / runs` 行数保留为 `1 / 1`，未破坏既有持久化数据
4. 烟测确认项目详情 `task_stats` 返回 `total=3`，并正确聚合 `pending=1 / waiting_human=1 / paused=1`
5. 烟测确认不存在的 `project_id` 创建任务会返回 `409`，项目挂载校验已生效

---

## 后续补测建议

1. Day02 接老板首页时，补项目列表聚合指标与页面展示链路的回归验证。
2. Day03 接项目规划入口时，补项目创建后自动映射任务的联调验证。
3. 若 Day01 实现继续演进，优先在 `runtime/orchestrator` 目录复跑 `python scripts/v3a_day01_project_smoke.py` 做最小回归。

