# Day12 审批回退重做与项目复盘收口

- 版本：`V3`
- 模块 / 提案：`模块C：交付件视图与审批闭环`
- 原始日期：`2026-04-17`
- 原始来源：`V3 正式版总纲 / 模块C：交付件视图与审批闭环 / Day12`
- 当前回填状态：**已完成**
- 回填口径：已在现有 Day09 ~ Day11 交付基础上补齐审批回退重做链路、项目复盘聚合接口与前端收口面板，严格收敛在 Day12 范围内。

---

## 今日目标

打通审批驳回后的回退、重做与复盘，避免审批流变成一次性死路。

---

## 当日交付

1. `runtime/orchestrator/app/services/approval_service.py`
2. `runtime/orchestrator/app/services/failure_review_service.py`
3. `runtime/orchestrator/app/services/decision_replay_service.py`
4. `runtime/orchestrator/app/api/routes/approvals.py`
5. `apps/web/src/features/approvals/ApprovalHistoryPanel.tsx`
6. `apps/web/src/features/projects/ProjectRetrospectivePanel.tsx`

---

## 验收点

1. 审批驳回后，交付件和项目阶段能进入可重做状态
2. 驳回原因、改动方向和重提记录被串联保存
3. 项目复盘页能汇总关键审批失败与返工原因
4. 审批闭环与失败复盘闭环打通
5. 用户可看见一条完整的“提交 -> 审批 -> 驳回/通过 -> 重做”链路

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：
  1. 在 `ApprovalService` 中补充了交付件级审批历史、返工轮次与项目审批返工回路计算能力，并复用现有审批闸门逻辑保持 Day10 / Day11 闭环连续。
  2. 在 `approvals.py` 中新增审批历史与项目复盘接口，把审批回退、失败复盘、最近失败运行统一暴露给前端。
  3. 在前端新增 `ApprovalHistoryPanel` 与 `ProjectRetrospectivePanel`，将审批重做链路、返工状态、失败聚类和最近失败运行收拢到老板视角页面中。
  4. 额外补充 `runtime/orchestrator/scripts/v3c_day12_approval_rework_retrospective_smoke.py`，验证“驳回 -> 重做版本 -> 重提审批 -> 通过 -> 项目复盘聚合”的最小烟测路径。
- 回填证据：
  1. `D:\AI-Dev-Orchestrator\runtime\orchestrator\.venv\Scripts\python.exe -X utf8 -m compileall app`
  2. `D:\AI-Dev-Orchestrator\runtime\orchestrator\.venv\Scripts\python.exe -X utf8 scripts/v3c_day12_approval_rework_retrospective_smoke.py`
  3. `D:\AI-Dev-Orchestrator\apps\web> npm.cmd run build`

---

## 关键产物路径

1. `runtime/orchestrator/app/services/approval_service.py`
2. `runtime/orchestrator/app/services/failure_review_service.py`
3. `runtime/orchestrator/app/services/decision_replay_service.py`
4. `runtime/orchestrator/app/api/routes/approvals.py`
5. `apps/web/src/features/approvals/ApprovalHistoryPanel.tsx`
6. `apps/web/src/features/projects/ProjectRetrospectivePanel.tsx`

---

## 上下游衔接

- 前一日：Day11 项目时间线与交付件对比视图
- 后一日：Day13 Skill注册中心与角色绑定
- 对应测试文档：`docs/01-版本冻结计划/V3/03-模块C-交付件视图与审批闭环/02-测试验证/Day12-审批回退重做与项目复盘收口-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；Day12 目标已在当前迭代内完成。

### 备注
1. Day12 完成后，V3 已具备“交付件 -> 审批 -> 驳回/补充 -> 重做 -> 再审批 -> 复盘聚合”的最小闭环。
2. 本次未扩展到 Day13 之后的 Skill 注册中心、项目记忆或策略引擎能力，严格按 Day12 收口。
