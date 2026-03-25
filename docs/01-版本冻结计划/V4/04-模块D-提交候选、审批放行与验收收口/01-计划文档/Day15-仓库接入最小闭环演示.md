# Day15 仓库接入最小闭环演示

- 版本：`V4`
- 模块 / 提案：`模块D：提交候选、审批放行与验收收口`
- 原始日期：`2026-05-06`
- 原始来源：`V4 正式版总纲 / 模块D：提交候选、审批放行与验收收口 / Day15`
- 当前回填状态：**已完成**
- 回填口径：Day15 已按冻结边界完成最小闭环演示：在本地场景串联 Day01~Day14，并新增 Day15 只读聚合视图与烟测；闭环终点保持“可审阅、可解释、可拒绝”，不触发真实 Git 写操作。

---

## 今日目标

用一个最小本地仓库场景把 Day01-Day14 串起来，验证从仓库绑定、文件定位、变更计划、风险守卫、验证、证据包到提交草案与放行判断的老板视角闭环；闭环止于“可审阅、可解释、可拒绝”，不以真实 Git 写动作为目标。

---

## 当日交付

1. `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`
2. `runtime/orchestrator/app/api/routes/repositories.py`
3. `runtime/orchestrator/app/api/routes/projects.py`
4. `runtime/orchestrator/app/api/routes/approvals.py`
5. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
6. `apps/web/src/features/repositories/DiffSummaryPage.tsx`
7. `apps/web/src/features/repositories/CommitDraftPanel.tsx`

---

## 验收点

1. 至少能跑通“绑定仓库 -> 刷新快照 -> 生成变更计划 -> 建立批次 -> 预检 -> 记录验证 -> 生成证据包 -> 形成提交草案 -> 展示放行判断”的最小链路
2. 关键接口、关键页面和关键状态流都有最小烟测证据
3. 如有未完成能力，必须在 Day15 演示中明确标记缺口，不伪造通过
4. 演示链路保持本地优先，不扩展到远程仓库推送、在线协作或真实 Git 写动作自动执行
5. Day15 只做闭环演示，不继续新增 Day16 之外的产品能力，也不把演示通过解释为已经具备真实 Git 自动化

---

## 演示边界（计划收敛）

1. Day15 是把 Day01-Day14 串起来做老板视角演示，不是新增仓库开发日。
2. 演示终点是“提交草案 + 放行检查单 + 缺口说明”齐备，不要求生成 commit hash、`push` 结果或 PR 记录。
3. 若上游任一能力未就绪，只记录缺口并终止演示，不以临时补开发的方式扩大 scope。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已在 Day15 范围内接通“绑定仓库 -> 刷新快照 -> 生成变更计划 -> 建立批次 -> 预检 -> 记录验证 -> 生成证据包 -> 形成提交草案 -> 展示放行判断”的最小闭环。后端新增 Day15 聚合接口、前端三处页面新增 Day15 闭环状态展示、并补齐 Day15 专用烟测脚本；演示全程保持只读，不执行真实 Git 写操作。
- 回填证据：
1. `runtime/orchestrator/app/api/routes/repositories.py` 新增 `GET /repositories/projects/{project_id}/day15-flow`，按步骤聚合 Day01~Day14 状态并输出 Day15 闭环快照
2. `runtime/orchestrator/app/api/routes/projects.py` 新增 `GET /projects/{project_id}/day15-repository-flow`，提供老板视角 Day15 总览状态
3. `runtime/orchestrator/app/api/routes/approvals.py` 新增 `GET /approvals/projects/{project_id}/day15-release-judgement`，输出 Day15 放行判断汇总
4. 前端在 `ProjectOverviewPage.tsx`、`DiffSummaryPage.tsx`、`CommitDraftPanel.tsx` 接入 Day15 状态卡片，分别展示闭环总览、证据步骤状态与放行判断状态
5. 新增烟测脚本 `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`，覆盖完整闭环与三条 Day15 聚合接口，并验证 `git_write_actions_triggered=false` 与 `head_unchanged=true`
6. Day15 范围明确收口：未进入 Day16+，未实现或触发真实 `git commit` / `push` / `PR` / `merge`

---

## 关键产物路径

1. `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`
2. `runtime/orchestrator/app/api/routes/repositories.py`
3. `runtime/orchestrator/app/api/routes/projects.py`
4. `runtime/orchestrator/app/api/routes/approvals.py`
5. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
6. `apps/web/src/features/repositories/DiffSummaryPage.tsx`
7. `apps/web/src/features/repositories/CommitDraftPanel.tsx`

---

## 上下游衔接

- 前一日：Day14 审批闸门与放行检查单
- 后一日：Day16 V4端到端验收与文档收口
- 对应测试文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/02-测试验证/Day15-仓库接入最小闭环演示-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day15 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day15 的重点是验证 V4 主线能否串起来，不再新增新的业务范围，也不把演示包装成真实 Git 自动化。
