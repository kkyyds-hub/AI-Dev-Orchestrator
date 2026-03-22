# Day10 验证运行记录与失败归因扩展

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-05-01`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day10`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day10 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

把仓库级验证结果做成结构化 `VerificationRun` 记录，明确是哪一轮批次、哪一组命令、因为什么原因失败或跳过。

---

## 当日交付

1. `runtime/orchestrator/app/domain/verification_run.py`
2. `runtime/orchestrator/app/repositories/verification_run_repository.py`
3. `runtime/orchestrator/app/services/verification_run_service.py`
4. `runtime/orchestrator/app/api/routes/runs.py`
5. `apps/web/src/features/run-log/VerificationRunPanel.tsx`
6. `runtime/orchestrator/scripts/v4c_day10_verification_run_smoke.py`

---

## 验收点

1. 验证运行记录可以关联仓库、变更计划、变更批次和命令模板
2. 每次运行至少能记录 `passed / failed / skipped`、耗时、输出摘要和失败类别
3. 项目时间线或运行视图可以看到最新一次验证结果
4. 失败原因口径和 Day08 的风险分类、V2 的失败复盘口径不冲突
5. Day10 只冻结验证运行记录，不提前扩展到差异视图与证据包

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day10 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day10 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/verification_run.py`
2. `runtime/orchestrator/app/repositories/verification_run_repository.py`
3. `runtime/orchestrator/app/services/verification_run_service.py`
4. `runtime/orchestrator/app/api/routes/runs.py`
5. `apps/web/src/features/run-log/VerificationRunPanel.tsx`
6. `runtime/orchestrator/scripts/v4c_day10_verification_run_smoke.py`

---

## 上下游衔接

- 前一日：Day09 仓库验证模板与项目命令基线
- 后一日：Day11 代码差异视图与验收证据包
- 对应测试文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/02-测试验证/Day10-验证运行记录与失败归因扩展-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day10 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day10 重点是验证结果结构化，不提前实现差异摘要和证据包。
