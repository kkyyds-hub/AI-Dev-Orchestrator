# Day12 回退重做与仓库复盘收口

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-05-03`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day12`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day12 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

为验证失败或审批驳回的仓库变更建立显式回退、重做和复盘收口路径，避免“改坏了只能重新来一遍”的黑盒状态。

---

## 当日交付

1. `runtime/orchestrator/app/services/change_rework_service.py`
2. `runtime/orchestrator/app/services/decision_replay_service.py`
3. `runtime/orchestrator/app/api/routes/approvals.py`
4. `apps/web/src/features/approvals/ChangeReworkPanel.tsx`
5. `apps/web/src/features/projects/ProjectTimelinePage.tsx`
6. `runtime/orchestrator/scripts/v4c_day12_change_rework_smoke.py`

---

## 验收点

1. 验证失败或审批驳回后，系统能明确标记为重做、回退建议或重新规划，而不是直接覆盖原记录
2. 回退 / 重做动作会保留原批次、原证据包和驳回原因的关联关系
3. 项目时间线和复盘视图可以看到一次仓库变更从计划到重做的全链路
4. 复盘口径与 V2 失败复盘、V3 项目时间线保持兼容
5. Day12 只冻结回退重做链路，不提前生成提交草案或放行检查单

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day12 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day12 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/services/change_rework_service.py`
2. `runtime/orchestrator/app/services/decision_replay_service.py`
3. `runtime/orchestrator/app/api/routes/approvals.py`
4. `apps/web/src/features/approvals/ChangeReworkPanel.tsx`
5. `apps/web/src/features/projects/ProjectTimelinePage.tsx`
6. `runtime/orchestrator/scripts/v4c_day12_change_rework_smoke.py`

---

## 上下游衔接

- 前一日：Day11 代码差异视图与验收证据包
- 后一日：Day13 提交草案与变更交付件
- 对应测试文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/02-测试验证/Day12-回退重做与仓库复盘收口-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day12 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day12 先把失败后的收口路径做清楚，不提前进入提交候选与放行阶段。
