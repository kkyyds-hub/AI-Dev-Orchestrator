# Day02 工作区扫描与目录快照基线 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/01-计划文档/Day02-工作区扫描与目录快照基线.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 可以手动刷新仓库快照，并看到目录数、文件数、语言分布和最近扫描时间
2. 默认忽略 `.git`、`node_modules`、`.venv`、`dist` 等噪声目录
3. 项目页面可以读取最新仓库快照摘要，并明确显示扫描是否成功
4. 快照结果只做结构化摘要，不提前扩展成完整代码索引或 AST 分析
5. 扫描异常会被显式记录，不伪装成“空仓库”

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/repository_snapshot.py`
3.    - `runtime/orchestrator/app/services/repository_scan_service.py`
4.    - `runtime/orchestrator/app/api/routes/repositories.py`
5.    - `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
6.    - `apps/web/src/features/repositories/components/RepositoryTreePanel.tsx`
7.    - `runtime/orchestrator/scripts/v4a_day02_repository_snapshot_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已按 Day02 范围完成后端扫描、快照摘要持久化、项目详情读取与前端展示，并完成编译、构建与 Day01 / Day02 烟测验证。
- 证据：
1. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe -m compileall app/api/routes/repositories.py app/api/routes/projects.py app/core/db_tables.py app/domain/project.py app/domain/repository_snapshot.py app/repositories/project_repository.py app/repositories/repository_snapshot_repository.py app/services/repository_scan_service.py scripts/v4a_day01_repository_binding_smoke.py scripts/v4a_day02_repository_snapshot_smoke.py`，新增与改动的 Day02 后端代码通过编译检查
2. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day01_repository_binding_smoke.py`，确认 Day02 接入后 Day01 的仓库绑定、路径边界与项目详情回写未发生回归
3. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day02_repository_snapshot_smoke.py`，确认手动刷新快照成功返回 `directory_count / file_count / language_breakdown / tree`，默认忽略 `.git`、`node_modules`、`.venv`、`dist` 等目录，且项目详情中的 `latest_repository_snapshot` 与仓库 API 载荷一致
4. Day02 烟测同时确认：当绑定仓库路径在刷新前被移走后，最新快照会以 `status=failed` 和显式 `scan_error` 持久化，而不是伪装成“空仓库”
5. 在 `apps/web` 目录执行 `npm run build`，确认新增的仓库快照项目页组件与目录树组件通过 TypeScript 编译和 Vite 生产构建

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. Day03 接分支会话时，优先复用 Day02 的最新快照摘要，不要把“快照可刷新”误读为允许真实分支切换或其他 Git 写操作。
3. 若后续调整忽略目录、树深度或项目页展示口径，先补 Day02 烟测，再回归验证前端构建。
