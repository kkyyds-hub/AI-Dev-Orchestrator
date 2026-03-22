# Day01 项目实体与生命周期建模

- 版本：`V3`
- 模块 / 提案：`模块A：项目级编排与老板入口`
- 原始日期：`2026-04-06`
- 原始来源：`V3 正式版总纲 / 模块A：项目级编排与老板入口 / Day01`
- 当前回填状态：**已完成**
- 回填口径：已按 Day01 范围完成 Project 最小闭环实现，并补充最小烟测验证。

---

## 今日目标

定义 `Project` 维度的最小领域模型、生命周期和与 `Task / Run` 的关系，让系统第一次能表达“一个项目由多条任务组成”。

---

## 当日交付

1. `runtime/orchestrator/app/domain/project.py`
2. `runtime/orchestrator/app/repositories/project_repository.py`
3. `runtime/orchestrator/app/services/project_service.py`
4. `runtime/orchestrator/app/core/db_tables.py`
5. `runtime/orchestrator/app/core/db.py`
6. `runtime/orchestrator/app/api/routes/projects.py`

---

## 验收点

1. 项目可以被创建、查询、列表化读取
2. 项目拥有明确的状态、阶段、摘要和基础统计字段
3. 任务可以挂到项目下，项目能看到聚合任务数量与状态分布
4. 数据库完成最小增量升级，不破坏现有 `Task / Run` 数据
5. API 字段口径与领域模型保持一致


---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已完成 Project 领域模型、数据库增量迁移、项目 API 与 `tasks.project_id` 关联接入，并通过 Day01 烟测验证最小闭环。
- 回填证据：
1. `runtime/orchestrator/app/domain/project.py` 已新增 `Project / ProjectStatus / ProjectStage / ProjectTaskStats`
2. `runtime/orchestrator/app/core/db_tables.py` 与 `runtime/orchestrator/app/core/db.py` 已新增 `projects` 表与 `tasks.project_id` 增量迁移
3. `runtime/orchestrator/app/repositories/project_repository.py` 与 `runtime/orchestrator/app/services/project_service.py` 已提供项目创建、列表、详情与任务聚合统计
4. `runtime/orchestrator/app/api/routes/projects.py` 与 `runtime/orchestrator/app/api/routes/tasks.py` 已接通项目创建 / 查询与任务挂载项目链路
5. `runtime/orchestrator/scripts/v3a_day01_project_smoke.py` 已验证旧 `Task / Run` 数据保留、项目聚合统计与任务挂载项目链路

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/project.py`
2. `runtime/orchestrator/app/repositories/project_repository.py`
3. `runtime/orchestrator/app/services/project_service.py`
4. `runtime/orchestrator/app/core/db_tables.py`
5. `runtime/orchestrator/app/core/db.py`
6. `runtime/orchestrator/app/api/routes/projects.py`


---

## 上下游衔接

- 前一日：无（V3 起点）
- 后一日：Day02 老板首页与项目总览看板
- 对应测试文档：`docs/01-版本冻结计划/V3/01-模块A-项目级编排与老板入口/02-测试验证/Day01-项目实体与生命周期建模-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；Day01 已按目标收口。

### 备注
1. Day01 已完成 V3 的 `Project` 地基，但未扩展到 Day02 的老板看板与 Day03 的项目规划入口。
