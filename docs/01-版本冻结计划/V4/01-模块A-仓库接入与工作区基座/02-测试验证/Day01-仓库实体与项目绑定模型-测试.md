# Day01 仓库实体与项目绑定模型 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/01-计划文档/Day01-仓库实体与项目绑定模型.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目可以绑定、查看和解除一个主仓库入口
2. 仓库记录至少包含 `root_path`、显示名、访问模式、默认基线分支和忽略规则摘要
3. 路径安全边界明确，禁止把仓库根目录指向不存在路径或越出允许工作区的目录
4. 项目详情和仓库 API 的字段口径保持一致
5. 数据库增量升级不破坏 V1 / V2 / V3 既有项目、任务和交付件数据

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/repository_workspace.py`
3.    - `runtime/orchestrator/app/repositories/repository_workspace_repository.py`
4.    - `runtime/orchestrator/app/services/repository_workspace_service.py`
5.    - `runtime/orchestrator/app/core/db_tables.py`
6.    - `runtime/orchestrator/app/core/db.py`
7.    - `runtime/orchestrator/app/api/routes/repositories.py`
8.    - `runtime/orchestrator/scripts/v4a_day01_repository_binding_smoke.py`

9. 检查后端路由、服务或项目流程是否已按计划接通。
10. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
11. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已按 Day01 范围完成实现，并完成编译校验与仓库绑定最小烟测验证。
- 证据：
1. 执行 `python -m compileall app/api/routes/repositories.py app/api/routes/projects.py app/api/router.py app/core/config.py app/core/db_tables.py app/domain/project.py app/domain/repository_workspace.py app/repositories/project_repository.py app/repositories/repository_workspace_repository.py app/services/repository_workspace_service.py scripts/v4a_day01_repository_binding_smoke.py`，新增与改动代码通过编译检查
2. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day01_repository_binding_smoke.py`，确认 `repository_workspaces` 表创建成功，且旧 `projects / tasks / deliverables` 数据行数仍保持 `1 / 1 / 1`
3. 烟测确认 `PUT /repositories/projects/{project_id}`、`GET /repositories/projects/{project_id}`、`DELETE /repositories/projects/{project_id}` 可完成绑定、查看和解除绑定主仓库入口
4. 烟测确认仓库记录返回 `root_path`、显示名、访问模式、默认基线分支、忽略规则摘要和 `allowed_workspace_root`，满足 Day01 字段口径
5. 烟测确认 `GET /projects/{project_id}` 返回的 `repository_workspace` 与仓库 API 返回载荷完全一致，项目详情字段口径已对齐
6. 烟测确认不存在路径会返回 `422` 且提示 `does not exist`，越出允许工作区的路径会返回 `422` 且提示 `allowed workspace root`

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. Day02 接工作区扫描时，优先复跑 `.\.venv\Scripts\python.exe scripts/v4a_day01_repository_binding_smoke.py`，确认 Day01 绑定与路径边界未被回归破坏。
3. Day03 接分支会话时，只允许在已绑定仓库路径内做只读状态记录，不把本日通过误读为可执行 Git 写操作。
