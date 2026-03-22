# Day02 工作区扫描与目录快照基线

- 版本：`V4`
- 模块 / 提案：`模块A：仓库接入与工作区基座`
- 原始日期：`2026-04-23`
- 原始来源：`V4 正式版总纲 / 模块A：仓库接入与工作区基座 / Day02`
- 当前回填状态：**已完成**
- 回填口径：已按 Day02 冻结范围完成“工作区最小扫描 + 目录快照摘要 + 项目页读取最新快照摘要”，未提前进入 Day03 及后续范围。

---

## 今日目标

建立仓库工作区的最小扫描能力，生成目录结构、语言分布、忽略目录和文件统计快照，让老板视角第一次看到“仓库当前长什么样”。

---

## 当日交付

1. `runtime/orchestrator/app/domain/repository_snapshot.py`
2. `runtime/orchestrator/app/services/repository_scan_service.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
5. `apps/web/src/features/repositories/components/RepositoryTreePanel.tsx`
6. `runtime/orchestrator/scripts/v4a_day02_repository_snapshot_smoke.py`

---

## 验收点

1. 可以手动刷新仓库快照，并看到目录数、文件数、语言分布和最近扫描时间
2. 默认忽略 `.git`、`node_modules`、`.venv`、`dist` 等噪声目录
3. 项目页面可以读取最新仓库快照摘要，并明确显示扫描是否成功
4. 快照结果只做结构化摘要，不提前扩展成完整代码索引或 AST 分析
5. 扫描异常会被显式记录，不伪装成“空仓库”

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已补齐 Day02 所需的只读扫描基线：后端新增 `RepositorySnapshot` 读模型、最小工作区扫描服务与快照持久化；仓库 API 支持手动刷新 / 读取最新快照；项目详情与项目页可直接读取最新快照摘要，并显式展示扫描成功或失败状态。整个回填过程未进入 Day03 的分支会话，也未扩展到文件定位、变更计划、AST 或真实 Git 写操作。
- 回填证据：
1. 新增 `runtime/orchestrator/app/domain/repository_snapshot.py`、`app/repositories/repository_snapshot_repository.py`、`app/services/repository_scan_service.py`，只按目录元数据生成结构化摘要，不读取全仓代码内容构建复杂索引
2. `runtime/orchestrator/app/api/routes/repositories.py` 新增 `POST /repositories/projects/{project_id}/snapshot/refresh` 与 `GET /repositories/projects/{project_id}/snapshot`，支持手动刷新和读取最新快照摘要
3. `runtime/orchestrator/app/api/routes/projects.py` 与 `app/repositories/project_repository.py` 已接入 `latest_repository_snapshot`，项目详情可直接读取最新快照摘要
4. 新增 `apps/web/src/features/repositories/RepositoryOverviewPage.tsx` 与 `components/RepositoryTreePanel.tsx`，项目页可展示仓库根目录、忽略目录、语言分布、目录树摘要和扫描失败信息
5. 已补充 `runtime/orchestrator/scripts/v4a_day02_repository_snapshot_smoke.py`，覆盖成功扫描、忽略目录、项目详情回写与失败快照显式记录

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/repository_snapshot.py`
2. `runtime/orchestrator/app/services/repository_scan_service.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
5. `apps/web/src/features/repositories/components/RepositoryTreePanel.tsx`
6. `runtime/orchestrator/scripts/v4a_day02_repository_snapshot_smoke.py`

---

## 上下游衔接

- 前一日：Day01 仓库实体与项目绑定模型
- 后一日：Day03 分支会话与仓库状态快照
- 对应测试文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/02-测试验证/Day02-工作区扫描与目录快照基线-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day02 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day02 只建立最小目录快照，不提前实现分支会话、文件定位或变更计划。
