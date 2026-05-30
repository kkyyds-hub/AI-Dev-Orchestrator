# AI Project Director Failure / Blocker Closure R1-G Audit

> 文档类型：Failure closure audit + evidence
> 审计日期：2026-05-30
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`cd8939c16d5c2f25e96e4c541aa3fc9a0651d52e`
> 前置阶段：R1-Fb v3 Runtime Pass (simulate Worker→Run)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-11（失败/阻塞是否有下一步）
> 修正：Codex 已补齐 `WORKER_SIMULATE_FAILURE_MODE=failed|blocked` 注入。本审计完成 failed + blocked 两组 live HTTP 全链路验证。

---

## 1. 审计范围

验证 CL-11：失败/阻塞任务是否有 retry / rework / human / replan / failure-review / decision-trace 等下一步机制。

### 1.1 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-worker-run-r1fb-20260529.md`
- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/api/routes/tasks.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/services/failure_review_service.py`
- `runtime/orchestrator/app/services/task_state_machine_service.py`
- `runtime/orchestrator/tests/test_approval_rework_task_creation.py`
- `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py`

---

## 2. Failure / Blocker API Inventory

### 2.1 Task Action Endpoints

| API | Method | Allowed Statuses | Transition | Evidence |
|---|---|---|---|---|
| `/tasks/{id}/retry` | POST | FAILED, BLOCKED | → PENDING | 409 from completed (correct guard) |
| `/tasks/{id}/pause` | POST | PENDING, FAILED, BLOCKED | → PAUSED | TASK-06 Pass |
| `/tasks/{id}/resume` | POST | PAUSED | → PENDING / WAITING_HUMAN | TASK-07 Pass |
| `/tasks/{id}/request-human` | POST | PENDING, FAILED, BLOCKED | → WAITING_HUMAN | TASK-08 Pass |
| `/tasks/{id}/resolve-human` | POST | WAITING_HUMAN | → PENDING | TASK-09 Pass |

### 2.2 Run Diagnostic Endpoints

| API | Method | Purpose | Evidence |
|---|---|---|---|
| `/runs/{run_id}/decision-trace` | GET | 含 failure_category, failure_review, routing evidence | Live HTTP 200 ✓ |
| `/runs/{run_id}/failure-review` | GET | 失败复盘记录 | Live HTTP 200 ✓ |

### 2.3 State Machine Guards

`task_state_machine_service.py` verified:
- `build_retry_transition`: FAILED/BLOCKED → PENDING ✓
- `build_pause_transition`: PENDING/FAILED/BLOCKED → PAUSED ✓
- `build_resume_transition`: PAUSED → PENDING ✓
- `build_request_human_review_transition`: PENDING/FAILED/BLOCKED → WAITING_HUMAN ✓
- `build_resolve_human_review_transition`: WAITING_HUMAN → PENDING ✓
- Invalid transitions → 409 Conflict (verified: retry on completed → 409, request-human on completed → 409)

---

## 3. Tests

### 3.1 Run

```bash
export WORKER_SIMULATE_EXECUTION_OVERRIDE=1
python -m pytest tests/test_approval_rework_task_creation.py tests/test_project_director_run_evidence_replay.py -v -q
```

**Result: 7 passed in 3.53s**

| Test | Coverage |
|---|---|
| test_reject_creates_one_rework_task_and_closed_approval_is_idempotent | approval reject → rework task |
| test_request_changes_becomes_compensating_rework | request_changes → compensating rework |
| test_closed_approval_action_has_no_compensating_task_side_effect | idempotent closed approval |
| test_rework_task_failure_rolls_back_approval_decision | atomic rollback |
| test_rework_task_has_source_draft_id_linking_to_approval | source tracing |
| test_approval_action_values_are_positive_negative_neutral | action value mapping |
| test_project_director_created_task_run_can_be_replayed_via_read_only_evidence_apis | run evidence replay |

---

## 4. Live HTTP Audit Results — Failed Mode

> Backend started with:
> `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`
> `WORKER_SIMULATE_FAILURE_MODE=failed`

| Step | API | Result | Key Data |
|---|---|---|---|
| 1 | POST /projects | 201 | project_id=`de6cc3ad-5f15-470d-b7e2-66bcf5527505` |
| 2 | POST /project-director/sessions | 201 | session created, 5 clarifying_questions |
| 3 | POST /sessions/{id}/answers | 200 | → ready_to_confirm |
| 4 | POST /sessions/{id}/confirm | 200 | → confirmed |
| 5 | POST /sessions/{id}/plan-versions | 201 | plan_version_id=`8268cdfe-...` |
| 6 | POST /project-director/plan-versions/{id}/confirm | 200 | → confirmed |
| 7 | POST /project-director/plan-versions/{id}/create-tasks | 201 | 6 tasks created |
| 8 | POST /workers/run-once?project_id=... | 200 | claimed=True, **task_status=failed**, **run_status=failed** |
| 9 | GET /tasks/{id} | 200 | status=failed, title="需求分析与范围确认" |
| 10 | GET /tasks/{id}/runs | 200 | 1 run: status=failed, failure_category=execution_failed |
| 11 | GET /runs/{id}/failure-review | **200** | failure_category=execution_failed, conclusion="Execution itself failed and the task was finalized as failed." |
| 12 | GET /runs/{id}/decision-trace | **200** | failure_category=execution_failed, 12 trace items, failure_review present |
| 13 | POST /tasks/{id}/retry | 200 | **previous_status=failed → current_status=pending** |
| 14 | GET /tasks/{id} readback | 200 | **status=pending** (confirmed retry succeeded) |

**Failed mode evidence IDs:**
- project_id: `de6cc3ad-5f15-470d-b7e2-66bcf5527505`
- task_id: `5b6ab14e-2dad-4b07-85cc-f7ae9e5b05ed`
- run_id: `d1655ad7-01ee-46fc-ba55-4dfea9a3fbbd`

---

## 5. Live HTTP Audit Results — Blocked Mode

> Backend restarted with:
> `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`
> `WORKER_SIMULATE_FAILURE_MODE=blocked`

| Step | API | Result | Key Data |
|---|---|---|---|
| 1-7 | Same as failed mode setup | 201/200 | project/ session/ plan/ tasks created |
| 8 | POST /workers/run-once?project_id=... | 200 | claimed=True, **task_status=blocked**, **run_status=cancelled** |
| 9 | GET /tasks/{id} | 200 | status=blocked, title="需求分析与范围确认" |
| 10 | GET /tasks/{id}/runs | 200 | 1 run: status=cancelled, failure_category=retry_limit_exceeded |
| 11 | GET /runs/{id}/failure-review | **200** | failure_category=retry_limit_exceeded, conclusion="Retry guard blocked this task because it exceeded the configured limit." |
| 12 | GET /runs/{id}/decision-trace | **200** | failure_category=retry_limit_exceeded, 12 trace items, failure_review present |
| 13 | POST /tasks/{id}/request-human | 200 | **previous_status=blocked → current_status=waiting_human**, human_status=requested |
| 14 | GET /tasks/{id} readback | 200 | **status=waiting_human** (confirmed) |
| 15 | POST /tasks/{id}/resolve-human | 200 | **previous_status=waiting_human → current_status=pending**, human_status=resolved |
| 16 | GET /tasks/{id} readback | 200 | **status=pending** (confirmed resolve-human succeeded) |

**Blocked mode evidence IDs:**
- project_id: `d7fea08a-b0d1-4fb6-a332-e607aa44ce50`
- task_id: `4c856a6a-1a01-48c2-a085-44ff233b2920`
- run_id: `88e0e97a-9fcb-4090-ba35-dd03c186bff1`

---

## 6. Simulate Failure Injection Verification

Codex commit `cd8939c` added `WORKER_SIMULATE_FAILURE_MODE` with `_normalize_simulate_failure_mode` in `executor_service.py` (only `failed` / `blocked` accepted, both require `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`).

- `failed` mode → `_simulate_execution()` returns `success=False` → `build_execution_resolution(execution_succeeded=False)` → task=FAILED, run=FAILED
- `blocked` mode → `_simulate_execution()` returns `success=False` with `simulate_failure_mode="blocked"` → `_finalize_execution()` calls `build_simulate_blocked_resolution()` → task=BLOCKED, run=CANCELLED

**Both paths verified via live HTTP API-only construction — no provider, no worker pool, no planning/apply, no git-commit.**

---

## 7. Mapping Conclusion

| Item | Status | Evidence |
|---|---|---|
| Retry mechanism (API + state machine) | **Runtime Pass** | POST /tasks/{id}/retry; FAILED→PENDING verified live HTTP |
| Human review mechanism | **Runtime Pass** | POST /tasks/{id}/request-human; BLOCKED→WAITING_HUMAN verified live HTTP |
| Resolve human mechanism | **Runtime Pass** | POST /tasks/{id}/resolve-human; WAITING_HUMAN→PENDING verified live HTTP |
| Failure-review endpoint | **Runtime Pass** | GET /runs/{id}/failure-review → 200 on both failed & blocked runs |
| Decision-trace endpoint | **Runtime Pass** | GET /runs/{id}/decision-trace → 200 on both failed & blocked runs |
| Approval rework chain | **Backend Pass** | 6 tests pass (test_approval_rework_task_creation.py) |
| Run evidence replay | **Backend Pass** | 1 test pass (test_project_director_run_evidence_replay.py) |
| State machine guards | **Backend Pass** | Validated by 16 tests (8 simulate + 2 evidence + 6 approval) |
| Frontend task action buttons | **API Pass** | TASK-06~12 previously verified |
| **Failed mode live HTTP** | **Runtime Pass** | task=failed, failure-review 200, decision-trace 200, retry→pending |
| **Blocked mode live HTTP** | **Runtime Pass** | task=blocked, failure-review 200, decision-trace 200, request-human→resolve-human→pending |

---

## 8. CL-11 Status

**Runtime Pass**

- Failed mode: full live HTTP evidence (project→session→plan→tasks→worker→failed task/run→failure-review→decision-trace→retry→pending readback)
- Blocked mode: full live HTTP evidence (project→session→plan→tasks→worker→blocked task/run→failure-review→decision-trace→request-human→waiting_human→resolve-human→pending readback)
- All tests pass: 16 passed (8 simulate + 2 evidence + 6 approval)
- State machine guards correct
- No provider, no worker pool, no planning/apply, no apply-local/git-commit

---

## 9. Gate Conclusion

### 9.1 R1-G Gate

**Runtime Pass**

Both failed + blocked live HTTP construction and verification completed. Full failure closure chain (failed/blocked Run → failure-review → decision-trace → retry/request-human/readback) confirmed by API-only evidence.

### 9.2 AI Project Director Total Closure

**仍为 Partial**

CL-12~CL-14, CL-15/16（治理中心端到端接入）, CL-18 尚未完成。
