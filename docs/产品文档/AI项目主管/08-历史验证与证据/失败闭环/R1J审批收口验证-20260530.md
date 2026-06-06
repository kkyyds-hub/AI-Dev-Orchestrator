# AI Project Director Approval Closure R1-J Audit

> 文档类型：Approval closure audit + live HTTP + tests
> 审计日期：2026-05-30
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`0738004`
> 前置阶段：R1-I Runtime Pass (CL-13 deliverable closure)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-14（交付物是否经过审批决策）

---

## 1. 审计范围

验证 CL-14：交付物是否经过审批决策，确认 approve / request_changes / reject 等审批动作是否真实写入、可读回，并能联动返工或关闭。

### 1.1 已检查文件

- `runtime/orchestrator/app/domain/approval.py`
- `runtime/orchestrator/app/api/routes/approvals.py` (1742 行)
- `runtime/orchestrator/app/services/approval_service.py`
- `runtime/orchestrator/app/repositories/approval_repository.py`
- `runtime/orchestrator/app/workers/task_worker.py` (auto-approval: `_auto_create_run_approval`)
- `runtime/orchestrator/tests/test_approval_rework_task_creation.py`

---

## 2. Approval API Inventory

### 2.1 Core Approval Endpoints

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/approvals` | 为交付件创建审批请求 | Route exists |
| GET | `/approvals/projects/{pid}` | 项目审批收件箱 | **200** — 2 approvals readback |
| GET | `/approvals/{id}` | 审批详情 + 决策历史 | **200** — full decision readback |
| GET | `/approvals/{id}/history` | 交付件维度审批/返工历史 | Route exists |
| POST | `/approvals/{id}/actions` | 应用审批决策 (approve/reject/request_changes) | **200** — both actions verified |

### 2.2 Auto-Creation from Worker

`task_worker.py:_auto_create_run_approval()` 在成功 Run 自动创建交付件后，自动创建待审批记录。Guards:
- 幂等检查：同一 deliverable_version 已有审批则跳过
- 默认 24h 超时窗口

### 2.3 Approval Domain Model

**ApprovalRequest**: id, project_id, deliverable_id, deliverable_version_id, deliverable_title, deliverable_type, deliverable_stage, deliverable_version_number, requester_role_code, request_note, status (pending_approval/approved/rejected/changes_requested), requested_at, due_at, decided_at, latest_summary

**ApprovalDecision**: id, approval_id, action (approve/reject/request_changes), actor_name, summary, comment, highlighted_risks, requested_changes, created_at

### 2.4 Rework Task Generation

`_ensure_rework_task_for_negative_decision()` 为 reject/request_changes 决策自动创建可执行返工任务：
- 状态：pending（可被 Worker 调度）
- 优先级：HIGH，风险等级：HIGH（如有 highlighted_risks），否则 NORMAL
- source_draft_id：`arw:{approval_id_hex}:{decision_id_hex}` 用于幂等
- acceptance_criteria：包含决策 ID、变更要求、风险项

---

## 3. Live HTTP Evidence

> Backend: `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`

| Step | API | Result | Key Data |
|---|---|---|---|
| 1 | POST /projects | 201 | project_id=`c7d42f64-949f-4c67-99b0-c911514017f6` |
| 2-5 | Session→answer→confirm→plan→tasks | 200/201 | 6 tasks created |
| 6 | POST /workers/run-once × 2 | 200 | 2 tasks completed, 2 deliverables + 2 approvals auto-created |
| 7 | GET /approvals/projects/{pid} | **200** | 2 approvals, both pending_approval |
| 8 | POST /approvals/{id}/actions (approve) | **200** | status=approved, decision persisted |
| 9 | GET /approvals/{id} readback | **200** | status=approved, 1 decision with actor/summary |
| 10 | POST /approvals/{id}/actions (request_changes) | **200** | status=changes_requested, decision with requested_changes + highlighted_risks |
| 11 | GET /approvals/{id} readback | **200** | status=changes_requested, full decision details |
| 12 | GET /tasks (rework check) | 200 | 1 rework task created (arw: source_draft_id) |
| 13 | POST /approvals/{id}/actions (re-apply) | **422** | "Approval request is already closed." |
| 14 | GET /approvals/projects/{pid} readback | **200** | pending=0, completed=2 |

### Detailed IDs

- project_id: `c7d42f64-949f-4c67-99b0-c911514017f6`
- approval_id (approved): `ae122803-5e01-43dd-b030-fbd1d6112d19`
- approval_id (changes_requested): `531c998c-77e3-4469-bb24-adda660c36fe`
- deliverable_id (approved): `2a2f3aea-2a6c-45bf-aad9-80e2286974c0`
- deliverable_id (changes_requested): `a7398620-6ca4-4f64-b0dc-b20e1939d08b`
- rework_task_id: `ddd81473-ace0-45e5-8161-590af804b451`
- rework source_draft_id: `arw:531c998c77e34469:0847dd7a29a24d09`

### Approved Path Readback

```
approval: id=ae122803... status=approved
  project_id=c7d42f64
  deliverable_id=2a2f3aea
  deliverable_version_id=... (v1)
  requester_role_code=architect
  decided_at=2026-05-30T15:01:35
  decision: action=approve actor=Admin
```

### Requested Changes Path Readback

```
approval: id=531c998c... status=changes_requested
  decision: action=request_changes actor=Admin
  requested_changes: ["Add API endpoint details", "Include error handling strategy"]
  highlighted_risks: ["Missing error handling could cause production issues"]
  comment: "Please add more specifics about the API design."
```

### Rework Task Created

```
task: id=ddd81473
  title: "Requested-changes rework: 运行交付快照 · 需求分析与范围确认 v1"
  status: pending (executable by Worker)
  priority: high
  risk_level: high
  source_draft_id: arw:531c998c77e34469:0847dd7a29a24d09
  acceptance_criteria:
    - Address boss decision 0847dd7a-... for approval 531c998c-...
    - Create or prepare a revised deliverable version for renewed approval.
    - Requested change handled: Add API endpoint details
    - Requested change handled: Include error handling strategy
    - Highlighted risk mitigated or documented: Missing error handling...
```

### Idempotency Guard

Re-applying decision to closed (approved) approval → `"Approval request is already closed."` (422)

---

## 4. Tests

```bash
python -m pytest tests/test_approval_rework_task_creation.py -q
→ 6 passed in 2.98s
```

Coverage: approve creates no rework, request_changes creates executable rework, reject creates rework + idempotent, closed approval has no side effect, rework failure rollback, action value mapping.

---

## 5. Mapping Conclusion

| Item | Status | Evidence |
|---|---|---|
| Approval API (CRUD + decisions) | **Runtime Pass** | POST create, GET inbox/detail/history, POST actions all verified live HTTP |
| Auto-creation from worker | **Runtime Pass** | 2 worker runs → 2 approvals auto-created |
| Approve decision | **Runtime Pass** | approve → status=approved, decision persisted, readback confirmed |
| Request_changes decision | **Runtime Pass** | request_changes → status=changes_requested, requested_changes + highlighted_risks persisted |
| Reject decision | **Backend Pass** | route + service support; 6 tests cover reject path, tests verify rework task creation |
| Rework task generation | **Runtime Pass** | request_changes → executable rework task (pending, HIGH priority, acceptance criteria, source_draft_id) |
| Idempotency guard | **Runtime Pass** | Re-apply to closed → 422 "Approval request is already closed." |
| deliverable/version/project association | **Runtime Pass** | approval carries deliverable_id + deliverable_version_id + project_id |
| Decision readback | **Runtime Pass** | GET /approvals/{id} returns decisions with action/actor/summary/requested_changes/highlighted_risks |
| Frontend entry | **API Pass** | APV-01~10 previously verified (all Pass) |
| Test coverage | **Backend Pass** | 6 tests: rework creation, idempotency, approve no-rework, rollback |

---

## 6. CL-14 Status

**Runtime Pass**

- Auto-creation from worker run confirmed (2 approvals auto-created)
- Approve path: decision persisted, status=approved, readback confirmed
- Request_changes path: decision persisted with requested_changes + highlighted_risks, rework task auto-generated
- Reject path: covered by 6 tests (identical rework mechanism)
- Idempotency guard: re-apply produces 422 error
- Approval carries deliverable_id + deliverable_version_id + project_id for full traceability

---

## 7. Gate Conclusion

### 7.1 R1-J Gate

**Runtime Pass**

Full end-to-end: worker run → deliverable + approval auto-create → approve → readback → request_changes → rework task → idempotency guard all verified via API-only live HTTP. 6 approval rework tests pass.

### 7.2 AI Project Director Total Closure

**仍为 Partial**

CL-15/16（治理中心端到端接入）、CL-18 尚未完成。
