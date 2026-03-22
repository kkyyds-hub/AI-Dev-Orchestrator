# Day12 审批回退重做与项目复盘收口 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/03-模块C-交付件视图与审批闭环/01-计划文档/Day12-审批回退重做与项目复盘收口.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 审批驳回后，交付件和项目阶段能进入可重做状态
2. 驳回原因、改动方向和重提记录被串联保存
3. 项目复盘页能汇总关键审批失败与返工原因
4. 审批闭环与失败复盘闭环打通
5. 用户可看见一条完整的“提交 -> 审批 -> 驳回/通过 -> 重做”链路

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
   - `runtime/orchestrator/app/services/approval_service.py`
   - `runtime/orchestrator/app/services/failure_review_service.py`
   - `runtime/orchestrator/app/services/decision_replay_service.py`
   - `runtime/orchestrator/app/api/routes/approvals.py`
   - `apps/web/src/features/approvals/ApprovalHistoryPanel.tsx`
   - `apps/web/src/features/projects/ProjectRetrospectivePanel.tsx`
2. 检查后端路由、服务或 Worker 链路是否已接通。
3. 检查前端页面、侧板或时间线是否能展示对应信息。
4. 若当日涉及状态流、审批或回退，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day12 所需的审批历史、返工状态、项目复盘聚合与前端展示均已接通，且未扩展到 Day13 之后能力。
- 证据：
  1. `D:\AI-Dev-Orchestrator\runtime\orchestrator\.venv\Scripts\python.exe -X utf8 -m compileall app`
     - 结果：通过。
     - 说明：确认 `approvals.py`、`approval_service.py`、`failure_review_service.py`、`decision_replay_service.py` 改动没有引入语法错误。
  2. `D:\AI-Dev-Orchestrator\runtime\orchestrator\.venv\Scripts\python.exe -X utf8 scripts/v3c_day12_approval_rework_retrospective_smoke.py`
     - 结果：通过。
     - 覆盖点：
       - `approve -> reject/request_changes -> rework version -> resubmit -> approve` 链路可回放；
       - `/approvals/{approval_id}/history` 能返回完整审批重做历史；
       - `/approvals/projects/{project_id}/retrospective` 能聚合审批返工回路与失败复盘信息。
  3. `D:\AI-Dev-Orchestrator\apps\web> npm.cmd run build`
     - 结果：通过。
     - 说明：确认 `ApprovalHistoryPanel`、`ProjectRetrospectivePanel` 以及相关 hooks/types/API 改造没有引入 TypeScript / Vite 构建错误。

---

## 后续补测建议

1. 若后续继续推进 Day13+，可在真实项目数据下补一轮多交付件、多次驳回、多次重提的链路回归。
2. 若审批动作继续扩展，可补充 UI 级截图或端到端脚本，验证历史链路和复盘卡片的显示稳定性。
3. 本次 Day12 已收口，不建议在同一任务中继续引入 Skill 注册中心、项目记忆或策略引擎相关补测项。
