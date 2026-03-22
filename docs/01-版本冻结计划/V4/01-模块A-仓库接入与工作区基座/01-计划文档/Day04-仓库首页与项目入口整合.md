# Day04 仓库首页与项目入口整合

- 版本：`V4`
- 模块 / 提案：`模块A：仓库接入与工作区基座`
- 原始日期：`2026-04-25`
- 原始来源：`V4 正式版总纲 / 模块A：仓库接入与工作区基座 / Day04`
- 当前回填状态：**已完成**
- 回填口径：已严格按 Day04 范围完成老板入口与项目详情页的仓库入口整合，统一返回仓库绑定 / 目录快照 / 变更会话摘要，并补齐最小烟测与文档回填；未提前跨入 Day05 文件定位索引、代码上下文包、变更计划、验证证据视图或任何真实 Git 写操作。

---

## 今日目标

把仓库绑定、目录快照和变更会话整合到老板入口与项目详情页，让仓库视角成为 V4 的第一层可见能力。

---

## 当日交付

1. `runtime/orchestrator/app/api/routes/console.py`
2. `runtime/orchestrator/app/api/routes/projects.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/repositories/RepositoryHomeCard.tsx`
5. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
6. `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py`

---

## 验收点

1. 老板入口和项目详情都能看见仓库是否已绑定、最新快照与当前变更会话
2. 未绑定仓库时，页面会明确提示下一步操作，而不是展示空白区域
3. 项目阶段统计、任务概览和仓库摘要可以在同一视图中联动查看
4. 仓库首页保留最小入口，不在 Day04 提前扩展到文件级编辑或验证证据视图
5. 页面字段、接口返回和领域对象命名保持统一

---

## 边界澄清

1. Day04 只消费 Day01-Day03 已存在的仓库绑定、目录快照和变更会话读模型，不新增文件级编辑能力。
2. Day04 的“仓库首页”是老板入口与项目详情中的最小摘要入口，不代表进入 Day05 的文件定位、代码上下文包或 AST 视图。
3. Day04 仍不在产品功能内执行任何真实 Git 写操作；仓库侧只读取绑定信息、快照与当前会话状态。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已完成老板首页仓库入口概览、项目列表仓库状态摘要、项目详情仓库首页卡片，以及 `/console/project-overview`、`/projects`、`/projects/{project_id}` 的统一字段回填；整个实现只展示仓库绑定 / 目录快照 / 变更会话摘要，不提前进入 Day05 及以后功能，也未在产品链路中加入任何真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/api/routes/console.py` 已为老板首页项目卡片补齐 `repository_workspace`、`latest_repository_snapshot`、`current_change_session` 三类仓库入口字段；`runtime/orchestrator/app/api/routes/projects.py` 已为项目列表与项目详情同步回填同名字段，确保接口命名一致
2. `apps/web/src/features/repositories/RepositoryHomeCard.tsx` 已新增最小仓库首页卡片，并接入 `apps/web/src/features/projects/ProjectOverviewPage.tsx`、`apps/web/src/features/projects/components/ProjectSummaryCards.tsx`、`apps/web/src/features/projects/components/ProjectTable.tsx`、`apps/web/src/features/repositories/RepositoryOverviewPage.tsx`，让老板入口与项目详情同时可见仓库绑定状态、最新快照和当前变更会话
3. `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py` 已新增 Day04 烟测，覆盖已绑定 / 未绑定项目在 `/console/project-overview`、`/projects`、`/projects/{project_id}` 上的仓库字段表现
4. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe -m compileall app/api/routes/console.py app/api/routes/projects.py scripts/v4a_day01_repository_binding_smoke.py scripts/v4a_day02_repository_snapshot_smoke.py scripts/v4a_day03_change_session_smoke.py scripts/v4a_day04_repository_home_smoke.py`，确认 Day04 涉及的后端路由与烟测脚本可通过编译检查
5. 在 `runtime/orchestrator` 目录依次执行 `.\.venv\Scripts\python.exe scripts/v4a_day01_repository_binding_smoke.py`、`.\.venv\Scripts\python.exe scripts/v4a_day02_repository_snapshot_smoke.py`、`.\.venv\Scripts\python.exe scripts/v4a_day03_change_session_smoke.py`、`.\.venv\Scripts\python.exe scripts/v4a_day04_repository_home_smoke.py`，确认 Day01-Day04 仓库绑定、快照、会话与首页整合链路全部通过
6. 在 `apps/web` 目录执行 `cmd /c npm run build`，确认老板首页、项目列表、仓库首页卡片与项目详情页的 TypeScript 编译和 Vite 生产构建通过

---

## 关键产物路径

1. `runtime/orchestrator/app/api/routes/console.py`
2. `runtime/orchestrator/app/api/routes/projects.py`
3. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
4. `apps/web/src/features/repositories/RepositoryHomeCard.tsx`
5. `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
6. `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py`

---

## 上下游衔接

- 前一日：Day03 分支会话与仓库状态快照
- 后一日：Day05 文件定位索引与代码上下文包
- 对应测试文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/02-测试验证/Day04-仓库首页与项目入口整合-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day04 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day04 只做仓库入口整合，不提前进入 Day05 的文件定位与代码上下文包。
