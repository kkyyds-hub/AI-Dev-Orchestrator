# Day07 变更批次与任务执行准备

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-28`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day07`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day07 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

把多个已确认的变更计划合并成可推进的 `ChangeBatch`，明确本轮开发准备改哪些文件、按什么顺序推进、是否存在文件重叠风险。

---

## 当日交付

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/services/change_batch_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
6. `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

---

## 验收点

1. 项目可以基于多个变更计划创建一个变更批次并查看其状态
2. 同一批次内的任务顺序、依赖关系和文件重叠风险有明确展示
3. 系统能限制同一项目同一时刻只有一个活跃变更批次，避免范围混乱
4. 批次摘要可以回写到项目视图与时间线
5. Day07 只建立执行准备模型，不提前触发审批守卫或真实仓库动作

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day07 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day07 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_batch.py`
2. `runtime/orchestrator/app/repositories/change_batch_repository.py`
3. `runtime/orchestrator/app/services/change_batch_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
6. `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

---

## 上下游衔接

- 前一日：Day06 仓库任务映射与变更计划草案
- 后一日：Day08 执行前风险守卫与人工确认
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day07-变更批次与任务执行准备-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day07 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day07 只冻结变更批次和执行准备，不提前实现 Day08 的执行前风险守卫。
