# Day13 提交草案与变更交付件

- 版本：`V4`
- 模块 / 提案：`模块D：提交候选、审批放行与验收收口`
- 原始日期：`2026-05-04`
- 原始来源：`V4 正式版总纲 / 模块D：提交候选、审批放行与验收收口 / Day13`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day13 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

把已经通过预检、验证并形成证据包的变更批次沉淀成 `CommitCandidate`，明确“准备提交什么、为什么这样提交、提交说明怎么写”，并把结果保持在可审阅草案层，不写入真实 Git 提交。

---

## 当日交付

1. `runtime/orchestrator/app/domain/commit_candidate.py`
2. `runtime/orchestrator/app/repositories/commit_candidate_repository.py`
3. `runtime/orchestrator/app/services/commit_candidate_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/CommitDraftPanel.tsx`
6. `runtime/orchestrator/scripts/v4d_day13_commit_candidate_smoke.py`

---

## 验收点

1. 已通过验证的变更批次可以生成一份结构化提交草案
2. 提交草案至少包含提交说明、影响范围、关联文件、验证摘要和关联交付件，并能被 Day14 直接消费
3. 同一批次的提交草案支持修订版本，不覆盖前一版说明
4. 提交草案只作为待放行交付件，不在 Day13 直接执行真实 `git commit`，也不写入 `.git` 或生成 commit hash
5. Day13 只冻结提交候选，不提前扩展到审批放行、远程仓库操作或任何自动提交动作

---

## 边界澄清

1. `CommitCandidate` 是可审阅的交付件草案，不是 Git commit object。
2. “修订版本”指草案版本历史，不等同于 `amend`、`rebase` 或其他 Git 重写动作。
3. Day13 的终点是给 Day14 提供可审批输入，而不是让仓库进入“已提交”状态。

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day13 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day13 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/commit_candidate.py`
2. `runtime/orchestrator/app/repositories/commit_candidate_repository.py`
3. `runtime/orchestrator/app/services/commit_candidate_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/CommitDraftPanel.tsx`
6. `runtime/orchestrator/scripts/v4d_day13_commit_candidate_smoke.py`

---

## 上下游衔接

- 前一日：Day12 回退重做与仓库复盘收口
- 后一日：Day14 审批闸门与放行检查单
- 对应测试文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/02-测试验证/Day13-提交草案与变更交付件-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day13 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day13 重点是把提交说明与交付件沉淀清楚，不提前执行真实提交、写入 `.git` 或远程操作。
