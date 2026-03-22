# Day04 仓库首页与项目入口整合 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/01-模块A-仓库接入与工作区基座/01-计划文档/Day04-仓库首页与项目入口整合.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 老板入口和项目详情都能看见仓库是否已绑定、最新快照与当前变更会话
2. 未绑定仓库时，页面会明确提示下一步操作，而不是展示空白区域
3. 项目阶段统计、任务概览和仓库摘要可以在同一视图中联动查看
4. 仓库首页保留最小入口，不在 Day04 提前扩展到文件级编辑或验证证据视图
5. 页面字段、接口返回和领域对象命名保持统一

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/api/routes/console.py`
3.    - `runtime/orchestrator/app/api/routes/projects.py`
4.    - `apps/web/src/features/projects/ProjectOverviewPage.tsx`
5.    - `apps/web/src/features/repositories/RepositoryHomeCard.tsx`
6.    - `apps/web/src/features/repositories/RepositoryOverviewPage.tsx`
7.    - `runtime/orchestrator/scripts/v4a_day04_repository_home_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：已按 Day04 范围完成老板入口与项目详情页的仓库入口整合，老板页/项目列表/项目详情都可查看仓库绑定、最新快照与当前变更会话；产品功能仍只读展示仓库摘要，不进入文件级编辑、验证证据视图或真实 Git 写操作。
- 证据：
1. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe -m compileall app/api/routes/console.py app/api/routes/projects.py scripts/v4a_day01_repository_binding_smoke.py scripts/v4a_day02_repository_snapshot_smoke.py scripts/v4a_day03_change_session_smoke.py scripts/v4a_day04_repository_home_smoke.py`，确认 Day04 涉及的后端路由与烟测脚本可通过编译检查
2. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day01_repository_binding_smoke.py`，确认 Day04 接入后 Day01 的仓库绑定与路径安全边界未回归
3. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day02_repository_snapshot_smoke.py`，确认 Day04 接入后 Day02 的目录快照、语言分布与项目详情快照回写未回归
4. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day03_change_session_smoke.py`，确认 Day04 接入后 Day03 的当前分支 / HEAD / 基线 / dirty workspace 会话能力未回归
5. 在 `runtime/orchestrator` 目录执行 `.\.venv\Scripts\python.exe scripts/v4a_day04_repository_home_smoke.py`，确认已绑定 / 未绑定项目在 `/console/project-overview`、`/projects` 与 `/projects/{project_id}` 上都能返回统一仓库字段，并在老板首页聚合结果中看见最新快照与当前变更会话
6. 在 `apps/web` 目录执行 `cmd /c npm run build`，确认 `RepositoryHomeCard`、项目总览页、项目列表仓库摘要与项目详情仓库首页组合后的 TypeScript 编译和 Vite 生产构建通过

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
