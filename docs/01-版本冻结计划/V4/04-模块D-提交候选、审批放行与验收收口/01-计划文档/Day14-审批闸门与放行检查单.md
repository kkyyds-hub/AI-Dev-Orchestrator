# Day14 审批闸门与放行检查单

- 版本：`V4`
- 模块 / 提案：`模块D：提交候选、审批放行与验收收口`
- 原始日期：`2026-05-05`
- 原始来源：`V4 正式版总纲 / 模块D：提交候选、审批放行与验收收口 / Day14`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day14 范围回填，不提前跨 Day 扩 scope。

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
6. `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`

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

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day14 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day14 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/services/repository_release_gate_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx`
5. `apps/web/src/features/approvals/ApprovalGatePage.tsx`
6. `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`

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
