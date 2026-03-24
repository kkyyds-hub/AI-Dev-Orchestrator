# Day12 回退重做与仓库复盘收口 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/01-计划文档/Day12-回退重做与仓库复盘收口.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 验证失败或审批驳回后，系统能明确标记为重做、回退建议或重新规划，而不是直接覆盖原记录
2. 回退 / 重做动作会保留原批次、原证据包和驳回原因的关联关系
3. 项目时间线和复盘视图可以看到一次仓库变更从计划到重做的全链路
4. 复盘口径与 V2 失败复盘、V3 项目时间线保持兼容
5. Day12 只冻结回退重做链路，不提前生成提交草案或放行检查单

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/change_rework_service.py`
3.    - `runtime/orchestrator/app/services/decision_replay_service.py`
4.    - `runtime/orchestrator/app/api/routes/approvals.py`
5.    - `apps/web/src/features/approvals/ChangeReworkPanel.tsx`
6.    - `apps/web/src/features/projects/ProjectTimelinePage.tsx`
7.    - `runtime/orchestrator/scripts/v4c_day12_change_rework_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day12 范围内后端聚合服务、接口、前端面板、时间线接入与烟测已闭环；未扩展到 Day13+ 提交候选与放行动作。
- 证据：
1. 关键产物已落地并接线：
   - `runtime/orchestrator/app/services/change_rework_service.py`
   - `runtime/orchestrator/app/services/decision_replay_service.py`
   - `runtime/orchestrator/app/api/routes/approvals.py`
   - `apps/web/src/features/approvals/ChangeReworkPanel.tsx`
   - `apps/web/src/features/projects/ProjectTimelinePage.tsx`
   - `runtime/orchestrator/scripts/v4c_day12_change_rework_smoke.py`
2. 后端检查：
   - `D:\\AI-Dev-Orchestrator\\runtime\\orchestrator\\.venv\\Scripts\\python.exe -X utf8 -m py_compile app/services/change_rework_service.py app/services/decision_replay_service.py app/api/routes/approvals.py scripts/v4c_day12_change_rework_smoke.py`
   - 结果：通过。
3. 前端构建：
   - `D:\\AI-Dev-Orchestrator\\apps\\web> npm.cmd run build`
   - 结果：通过（仅有 Vite chunk size warning，属于既有告警，不影响 Day12 功能验收）。
4. Day12 烟测：
   - `D:\\AI-Dev-Orchestrator\\runtime\\orchestrator\\.venv\\Scripts\\python.exe -X utf8 scripts/v4c_day12_change_rework_smoke.py`
   - 结果：通过。
   - 关键断言：
     - `change_rework_total_items=1`
     - `approval_item_recommendation=rollback`
     - `approval_item_status=rework_required`
     - `approval_item_evidence_package_key` 非空
     - `timeline_event_types` 包含 `deliverable/preflight/approval`
     - `retrospective_negative_cycles=1`

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。
