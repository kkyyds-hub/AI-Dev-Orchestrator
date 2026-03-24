# Day14 审批闸门与放行检查单

- 版本：`V4`
- 模块 / 提案：`模块D：提交候选、审批放行与验收收口`
- 原始日期：`2026-05-05`
- 原始来源：`V4 正式版总纲 / 模块D：提交候选、审批放行与验收收口 / Day14`
- 当前回填状态：**已完成**
- 回填口径：Day14 已按冻结边界完成放行检查单汇总、缺口阻断、审批动作记录与前后端接线；审批通过仅代表放行资格成立，不自动触发真实 Git 写动作。

---

## 今日目标

把仓库接入链路中的绑定、快照、预检、验证、证据包和提交草案汇总为最终放行检查单，形成老板可决策的 V4 闸门；闸门通过不自动执行仓库写动作。

---

## 当日交付

1. `runtime/orchestrator/app/services/repository_release_gate_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx`
5. `apps/web/src/features/approvals/ApprovalGatePage.tsx`
6. `apps/web/src/features/approvals/RepositoryReleaseGatePanel.tsx`
7. `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`

---

## 验收点

1. 放行检查单至少覆盖仓库绑定、快照新鲜度、变更计划、风险预检、验证结果、差异证据和提交草案
2. 任一关键项缺失时，审批闸门会显式阻断并给出缺口说明
3. 审批动作会记录通过、驳回、补证据等决策及其原因
4. 放行闸门仍保持本地优先，不在 Day14 扩展到自动 `push`、自动 PR、自动 `merge`，也不因审批通过而自动执行 `git commit`
5. 审批口径与 V3 的交付件 / 审批链路保持兼容

---

## 边界澄清

1. Day14 的审批通过只表示“放行资格成立”，不等于系统自动写仓库或自动发起远程动作。
2. Day14 只统一检查单和决策记录，不回头补做 Day13 的真实提交，也不提前进入 Day15 演示联调。
3. 任何真实 Git 写操作仍需人工显式发起，且不在当前冻结文档承诺范围内。

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已落地 Day14 放行检查单服务与审批动作链路：后端汇总七项关键检查并在缺口时阻断通过动作；前端新增 Day14 面板展示检查单与审批记录；审批通过只形成“放行资格成立”状态，不自动执行真实 Git 写操作。
- 回填证据：
1. 后端新增 `runtime/orchestrator/app/services/repository_release_gate_service.py`，汇总仓库绑定、快照新鲜度、变更计划、风险预检、验证结果、差异证据、提交草案七项检查单，并输出 `blocked / pending_approval / approved / rejected / changes_requested`
2. `runtime/orchestrator/app/api/routes/approvals.py` 新增 Day14 审批路由：`GET /approvals/projects/{project_id}/repository-release-gate`、`GET /approvals/repository-release-gate/{change_batch_id}`、`POST /approvals/repository-release-gate/{change_batch_id}/actions`，支持通过 / 驳回 / 补证据动作与原因记录
3. `runtime/orchestrator/app/api/routes/repositories.py` 新增 Day14 查询路由：`GET /repositories/projects/{project_id}/release-gates`、`GET /repositories/change-batches/{change_batch_id}/release-checklist`，保持与仓库页链路兼容
4. 前端新增 `apps/web/src/features/approvals/RepositoryReleaseGatePanel.tsx` 与 `RepositoryReleaseChecklist.tsx`，并在 `ApprovalInboxPage.tsx` 接入 Day14 展示与审批动作表单；新增 `ApprovalGatePage.tsx` 兼容导出
5. 新增烟测脚本 `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`，验证“关键项缺失时阻断 + 三类审批动作记录 + 通过后仅放行资格成立且 `head_unchanged=true`”
6. Day14 仍不扩展到 Day15 最小闭环演示，不实现自动 `git commit` / `push` / `PR` / `merge`

---

## 关键产物路径

1. `runtime/orchestrator/app/services/repository_release_gate_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx`
5. `apps/web/src/features/approvals/ApprovalGatePage.tsx`
6. `apps/web/src/features/approvals/RepositoryReleaseGatePanel.tsx`
7. `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`

---

## 上下游衔接

- 前一日：Day13 提交草案与变更交付件
- 后一日：Day15 仓库接入最小闭环演示
- 对应测试文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/02-测试验证/Day14-审批闸门与放行检查单-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day14 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day14 只冻结最终放行检查单与审批记录，不提前把远程仓库自动化或自动提交纳入范围。
