# Day12 回退重做与仓库复盘收口

- 版本：`V4`
- 模块 / 提案：`模块C：验证基线与证据沉淀`
- 原始日期：`2026-05-03`
- 原始来源：`V4 正式版总纲 / 模块C：验证基线与证据沉淀 / Day12`
- 当前回填状态：**已完成**
- 回填口径：已按 Day12 冻结边界完成“验证失败 / 审批驳回 -> 回退重做 -> 复盘收口”闭环，仅覆盖 Day12，不提前进入 Day13+ 提交候选与放行阶段。

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

- 当前结论：**已完成**
- 回填说明：
1. 新增 `change_rework_service.py`，将 ChangeBatch、VerificationRun、审批返工回路与失败复盘聚合为 Day12 回退重做快照，显式输出重做/回退/重规划建议，并保留原批次与驳回原因关联。
2. 扩展 `approvals.py`，新增 `/approvals/projects/{project_id}/change-rework` 接口，返回项目级“计划 -> 验证 -> 驳回/失败 -> 回退重做”链路数据。
3. 扩展 `decision_replay_service.py`，补充按任务索引失败历史能力，供 Day12 回退链路构建复用，同时保持 V3 复盘口径兼容。
4. 前端新增 `ChangeReworkPanel.tsx` 并接入 `ProjectTimelinePage.tsx`，在时间线页直接展示回退重做链路与证据包键反查入口。
5. 新增 `v4c_day12_change_rework_smoke.py`，覆盖批次预检驳回、验证失败、审批驳回、回退聚合接口、项目时间线与复盘接口联动断言。
- 回填证据：
1. `D:\\AI-Dev-Orchestrator\\runtime\\orchestrator\\.venv\\Scripts\\python.exe -X utf8 -m py_compile app/services/change_rework_service.py app/services/decision_replay_service.py app/api/routes/approvals.py scripts/v4c_day12_change_rework_smoke.py`（通过）
2. `D:\\AI-Dev-Orchestrator\\apps\\web> npm.cmd run build`（通过；保留既有 chunk size warning，不影响 Day12 验收）
3. `D:\\AI-Dev-Orchestrator\\runtime\\orchestrator\\.venv\\Scripts\\python.exe -X utf8 scripts/v4c_day12_change_rework_smoke.py`（通过）
   - 关键结果：`change_rework_total_items=1`、`approval_item_recommendation=rollback`、`approval_item_status=rework_required`、`approval_item_evidence_package_key` 非空、`timeline_event_types` 包含 `deliverable/preflight/approval`、`retrospective_negative_cycles=1`。

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
