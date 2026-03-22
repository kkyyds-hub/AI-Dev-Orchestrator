# Day01 仓库实体与项目绑定模型

- 版本：`V4`
- 模块 / 提案：`模块A：仓库接入与工作区基座`
- 原始日期：`2026-04-22`
- 原始来源：`V4 正式版总纲 / 模块A：仓库接入与工作区基座 / Day01`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day01 范围完成仓库实体、项目绑定关系、路径安全边界、最小仓库 API 与烟测回填，未提前进入 Day02 及以后范围。

---

## 今日目标

定义 `RepositoryWorkspace` 的最小领域模型、项目绑定关系和路径安全边界，让系统第一次能明确表达“一个项目绑定一个本地主仓库入口”。

---

## 当日交付

1. `runtime/orchestrator/app/domain/repository_workspace.py`
2. `runtime/orchestrator/app/repositories/repository_workspace_repository.py`
3. `runtime/orchestrator/app/services/repository_workspace_service.py`
4. `runtime/orchestrator/app/domain/project.py`
5. `runtime/orchestrator/app/repositories/project_repository.py`
6. `runtime/orchestrator/app/core/config.py`
7. `runtime/orchestrator/app/core/db_tables.py`
8. `runtime/orchestrator/app/api/routes/repositories.py`
9. `runtime/orchestrator/app/api/routes/projects.py`
10. `runtime/orchestrator/app/api/router.py`
11. `runtime/orchestrator/scripts/v4a_day01_repository_binding_smoke.py`

---

## 验收点

1. 项目可以绑定、查看和解除一个主仓库入口
2. 仓库记录至少包含 `root_path`、显示名、访问模式、默认基线分支和忽略规则摘要
3. 路径安全边界明确，禁止把仓库根目录指向不存在路径或越出允许工作区的目录
4. 项目详情和仓库 API 的字段口径保持一致
5. 数据库增量升级不破坏 V1 / V2 / V3 既有项目、任务和交付件数据

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已完成 `RepositoryWorkspace` 最小领域模型、项目级单主仓库绑定、路径安全边界校验、项目详情回写和最小 API / 烟测闭环；未提前实现目录扫描、分支状态快照、Git 写操作或仓库首页。
- 回填证据：
1. `runtime/orchestrator/app/domain/repository_workspace.py` 已新增 `RepositoryWorkspace / RepositoryAccessMode`，明确 `root_path`、显示名、访问模式、默认基线分支、忽略规则摘要和允许工作区根目录字段
2. `runtime/orchestrator/app/services/repository_workspace_service.py` 已实现项目绑定、读取、解除绑定，以及“路径存在 / 必须为绝对目录 / 不越过允许工作区 / 不指向 runtime_data / 不指向系统临时目录 / 必须存在 .git”边界校验
3. `runtime/orchestrator/app/core/db_tables.py` 已新增 `repository_workspaces` 表，并通过 `project_id` 唯一约束表达“一个项目绑定一个本地主仓库入口”
4. `runtime/orchestrator/app/domain/project.py`、`runtime/orchestrator/app/repositories/project_repository.py`、`runtime/orchestrator/app/api/routes/projects.py` 已把 `repository_workspace` 回写到 `Project` / 项目详情响应，确保项目详情与仓库 API 字段口径一致
5. `runtime/orchestrator/app/api/routes/repositories.py` 与 `runtime/orchestrator/app/api/router.py` 已接通 `PUT /repositories/projects/{project_id}`、`GET /repositories/projects/{project_id}`、`DELETE /repositories/projects/{project_id}` 最小链路
6. `runtime/orchestrator/scripts/v4a_day01_repository_binding_smoke.py` 已覆盖旧项目 / 任务 / 交付件数据保留、仓库绑定 / 查看 / 解绑，以及不存在路径 / 越界路径拦截
7. `runtime/orchestrator/app/core/db.py` 与 `runtime/orchestrator/app/services/project_service.py` 复用 V3 已有基座即可满足 Day01，无需为本日额外改动代码

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/repository_workspace.py`
2. `runtime/orchestrator/app/repositories/repository_workspace_repository.py`
3. `runtime/orchestrator/app/services/repository_workspace_service.py`
4. `runtime/orchestrator/app/domain/project.py`
5. `runtime/orchestrator/app/repositories/project_repository.py`
6. `runtime/orchestrator/app/core/config.py`
7. `runtime/orchestrator/app/core/db_tables.py`
8. `runtime/orchestrator/app/api/routes/repositories.py`
9. `runtime/orchestrator/app/api/routes/projects.py`
10. `runtime/orchestrator/app/api/router.py`
11. `runtime/orchestrator/scripts/v4a_day01_repository_binding_smoke.py`

---

## 上下游衔接

- 前一日：无（V4 起点）
- 后一日：Day02 工作区扫描与目录快照基线
- 对应测试文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/02-测试验证/Day01-仓库实体与项目绑定模型-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；Day01 已按目标收口。

### 备注
1. Day01 已完成项目与仓库绑定模型，但仍未进入 Day02 的目录扫描、Day03 的分支会话或任何真实 Git 写操作。
