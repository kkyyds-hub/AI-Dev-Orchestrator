# Day09 仓库验证模板与项目命令基线

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-04-30`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day09`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day09 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

为仓库建立可复用的 `build / test / lint / typecheck` 命令模板，让每个变更计划都能引用稳定的验证基线，而不是临时拼接命令。

---

## 当日交付

1. `runtime/orchestrator/app/domain/repository_verification.py`
2. `runtime/orchestrator/app/repositories/repository_verification_repository.py`
3. `runtime/orchestrator/app/services/repository_verification_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
6. `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`

---

## 验收点

1. 仓库可以配置最小验证命令模板，并区分 `build / test / lint / typecheck` 类别
2. 变更计划或变更批次可以引用其中一个或多个命令模板
3. 命令模板至少记录命令文本、工作目录、超时、是否默认启用等字段
4. 项目或仓库页面可以查看当前验证基线和最后更新时间
5. Day09 只冻结验证模板，不提前记录验证运行结果或差异证据

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day09 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day09 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/repository_verification.py`
2. `runtime/orchestrator/app/repositories/repository_verification_repository.py`
3. `runtime/orchestrator/app/services/repository_verification_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
6. `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`

---

## 上下游衔接

- 前一日：Day08 执行前风险守卫与人工确认
- 后一日：Day10 验证运行记录与失败归因扩展
- 对应测试文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/02-测试验证/Day09-仓库验证模板与项目命令基线-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day09 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day09 先把验证命令基线定稳，不提前实现 Day10 的验证运行记录。
