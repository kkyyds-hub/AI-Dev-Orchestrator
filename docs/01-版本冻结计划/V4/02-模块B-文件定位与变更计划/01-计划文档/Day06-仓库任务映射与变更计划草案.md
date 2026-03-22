# Day06 仓库任务映射与变更计划草案

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-27`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day06`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day06 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

把项目任务、交付件和候选文件集合映射成结构化 `ChangePlan`，让“要改什么、为什么改、改完怎么验”第一次有统一记录。

---

## 当日交付

1. `runtime/orchestrator/app/domain/change_plan.py`
2. `runtime/orchestrator/app/repositories/change_plan_repository.py`
3. `runtime/orchestrator/app/services/change_plan_service.py`
4. `runtime/orchestrator/app/api/routes/planning.py`
5. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
6. `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`

---

## 验收点

1. 任务可以创建、查看和更新一份变更计划草案
2. 变更计划至少包含目标文件、预期动作、风险说明、验证命令引用和关联交付件
3. 同一个交付件可以记录多版变更计划草案，保留版本时间线
4. 项目详情能反查任务与变更计划的映射关系
5. Day06 只冻结计划草案，不提前进入批次调度和风险预检

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day06 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day06 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/change_plan.py`
2. `runtime/orchestrator/app/repositories/change_plan_repository.py`
3. `runtime/orchestrator/app/services/change_plan_service.py`
4. `runtime/orchestrator/app/api/routes/planning.py`
5. `apps/web/src/features/projects/ChangePlanDrawer.tsx`
6. `runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py`

---

## 上下游衔接

- 前一日：Day05 文件定位索引与代码上下文包
- 后一日：Day07 变更批次与任务执行准备
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day06-仓库任务映射与变更计划草案-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day06 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day06 只做任务到变更计划的结构化映射，不提前实现批次编排。
