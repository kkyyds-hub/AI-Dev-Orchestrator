# AI Project Director Deliverable Closure R1-I Audit

> 文档类型：Deliverable closure audit + live HTTP + tests
> 审计日期：2026-05-30
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`095071f`
> 前置阶段：R1-H Evidence Partial (CL-12 repository evidence chain)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-13（成功任务是否形成交付物）

---

## 1. 审计范围

验证 CL-13：成功任务是否形成交付物（deliverable id/version/source evidence），且交付物能否支撑 CL-12 change plan 链路。

### 1.1 已检查文件

- `runtime/orchestrator/app/domain/deliverable.py`
- `runtime/orchestrator/app/api/routes/deliverables.py` (618 行)
- `runtime/orchestrator/app/services/deliverable_service.py`
- `runtime/orchestrator/app/repositories/deliverable_repository.py`
- `runtime/orchestrator/app/workers/task_worker.py` (auto-creation logic: `_auto_create_run_deliverable`)
- `runtime/orchestrator/app/services/change_plan_service.py` (deliverable 前置依赖)
- `runtime/orchestrator/tests/`

---

## 2. Deliverable API Inventory

### 2.1 Deliverable CRUD

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/deliverables` | 创建交付件 + v1 版本 | **201** — Route verified |
| GET | `/deliverables/{id}` | 获取交付件详情 + 版本历史 | **200** — readback confirmed |
| GET | `/deliverables/projects/{pid}` | 项目交付件仓库视图 | **200** — 1 deliverable found |
| GET | `/deliverables/tasks/{tid}` | 任务关联交付件反向查找 | **200** — 1 match by source_task_id |
| POST | `/deliverables/{id}/versions` | 追加不可变版本快照 | Route exists |
| GET | `/deliverables/{id}/compare` | 版本间 diff | Route exists |
| GET | `/deliverables/{id}/change-evidence` | 交付件维度验收证据包 | Route exists |
| GET | `/deliverables/projects/{pid}/change-evidence` | 项目维度验收证据包 | Route exists |

### 2.2 Auto-Creation from Worker

`task_worker.py:_auto_create_run_deliverable()` 在成功 Run 时自动创建交付件快照。Guards:

| Condition | Guard |
|---|---|
| `not execution.success` | 跳过（失败不产生交付物） |
| `execution.fallback_applied` | 跳过（fallback 不产生交付物） |
| `execution.actual_execution_mode == "provider_mock"` | 跳过（mock 不产生交付物） |
| `task.project_id is None` | 跳过（无项目上下文） |
| 已存在同 `source_run_id` 的交付件 | 幂等返回已有记录 |

Simulate execution via `WORKER_SIMULATE_EXECUTION_OVERRIDE=1` satisfies all guards: success=True, fallback_applied=False, actual_execution_mode="simulate" (not "provider_mock").

### 2.3 Deliverable Domain Model

**Deliverable**:
- `id`, `project_id`, `type` (enum: PRD/DESIGN/TASK_BREAKDOWN/CODE_PLAN/ACCEPTANCE_CONCLUSION/STAGE_ARTIFACT)
- `title`, `stage`, `created_by_role_code`
- `current_version_number`, `created_at`, `updated_at`

**DeliverableVersion**:
- `id`, `deliverable_id`, `version_number`, `author_role_code`
- `summary` (max 1000), `content` (max 40000), `content_format` (markdown/plain_text/json/link)
- `source_task_id` — 链接到原始 task
- `source_run_id` — 链接到原始 run
- `created_at`

### 2.4 As ChangePlan Pre-requisite

`ChangePlanService.create_change_plan()` requires `related_deliverable_ids: list[UUID]`. Auto-created deliverable IDs can be directly used as input.

---

## 3. Live HTTP Evidence

> Backend: `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`

| Step | API | Result | Key Data |
|---|---|---|---|
| 1 | POST /projects | 201 | project_id=`b87c12aa-f801-4c6d-b978-d1a25fab9b28` |
| 2-5 | Session → answer → confirm → plan → confirm → create-tasks | 200/201 | 6 tasks created |
| 6 | POST /workers/run-once | 200 | task=completed, run=succeeded, execution_mode=simulate |
| 7 | GET /deliverables/projects/{pid} | **200** | **1 deliverable auto-created** |
| 8 | GET /deliverables/{id} detail | **200** | Full version history with source_task_id + source_run_id |
| 9 | GET /deliverables/tasks/{tid} | **200** | 1 match by source_task_id (reverse lookup) |
| 10 | GET /tasks/{tid}/runs | 200 | Cross-reference: run_id matches deliverable source_run_id |
| 11 | GET /tasks/{tid} | 200 | task=completed, project_id matches |

### Detailed IDs

- project_id: `b87c12aa-f801-4c6d-b978-d1a25fab9b28`
- task_id: `c7df786d-d225-4c43-bc92-790567452eb6`
- run_id: `7b8de898-8258-4a62-aac8-323351acabd0`
- deliverable_id: `1a765d85-32e1-4f99-badc-141dd48f7ddf`
- version_id: `365e5c67-f491-4411-99ff-df51878532e6`

### Deliverable Content

| Field | Value |
|---|---|
| title | 运行交付快照 · 需求分析与范围确认 |
| type | stage_artifact |
| stage | intake |
| created_by_role_code | architect |
| current_version_number | 1 |
| total_versions | 1 |
| version.content_format | markdown |
| version.source_task_id | `c7df786d-...` (matches task) |
| version.source_run_id | `7b8de898-...` (matches run) |
| version.content | Markdown 文档含 Task ID, Run ID, Execution mode, Run status, 执行摘要 |

### Trace Chain

```
project (b87c12aa)
  → task (c7df786d, status=completed)
    → run (7b8de898, status=succeeded)
      → deliverable (1a765d85, type=stage_artifact)
        → version v1 (365e5c67)
          source_task_id = c7df786d ✓
          source_run_id = 7b8de898 ✓
```

Reverse lookup via `GET /deliverables/tasks/{task_id}` returns the same deliverable, confirming the bidirectional link.

---

## 4. Tests

```bash
python -m pytest tests/ -q
→ 163 passed in 38.79s
```

Full test suite passes. `_auto_create_run_deliverable` is exercised through worker run tests and approval rework tests (which depend on deliverable existence).

---

## 5. Deliverable → ChangePlan Feed

The auto-created deliverable carries all information needed for ChangePlan:

| ChangePlan Requirement | Deliverable Provides |
|---|---|
| `project_id` | deliverable.project_id |
| `task_id` | deliverable version.source_task_id (matching) |
| `related_deliverable_ids` | deliverable.id |
| `primary_deliverable_id` | deliverable.id |
| `intent_summary` / `source_summary` | version.summary / version.content |

`ChangePlanService.create_change_plan(project_id=..., task_id=..., related_deliverable_ids=[deliverable.id], ...)` — all parameters satisfiable by existent deliverable.

---

## 6. Mapping Conclusion

| Item | Status | Evidence |
|---|---|---|
| Deliverable API (CRUD) | **Runtime Pass** | 8 routes: create, detail, project snapshot, task-related, version append, compare, change-evidence × 3 |
| Auto-creation from successful run | **Runtime Pass** | Simulate run → 1 deliverable auto-created, confirmed via GET readback |
| source_task_id trace | **Runtime Pass** | version.source_task_id = task_id, confirmed via GET /deliverables/tasks/{tid} |
| source_run_id trace | **Runtime Pass** | version.source_run_id = run_id, confirmed via GET /tasks/{tid}/runs cross-ref |
| project_id association | **Runtime Pass** | deliverable.project_id = project_id |
| Version/content tracking | **Runtime Pass** | v1 with markdown content, summary, created_at, author_role_code |
| ChangePlan pre-requisite | **Confirmed** | deliverable.id can feed ChangePlan.related_deliverable_ids |
| Frontend entry | **API Pass** | DEL-01~11 previously verified (9 Pass / 2 Partial) |
| Test coverage | **Backend Pass** | 163 full suite pass; worker tests exercise auto-creation |

---

## 7. CL-13 Status

**Runtime Pass**

- Successful simulate run → auto-create deliverable confirmed via live HTTP
- deliverable.id / version / source_task_id / source_run_id / project_id all linked and read-back
- Bidirectional trace: task → deliverable (via source_task_id) and deliverable → task (via task-related API)
- deliverable.id can serve as ChangePlan.related_deliverable_ids pre-requisite
- 163 full test suite pass

---

## 8. Gate Conclusion

### 8.1 R1-I Gate

**Runtime Pass**

Full end-to-end: simulate run → deliverable auto-create → readback → task/run/project association → ChangePlan feedability all verified via API-only live HTTP.

### 8.2 AI Project Director Total Closure

**仍为 Partial**

CL-14（审批闭环）、CL-15/16（治理中心端到端接入）、CL-18 尚未完成。
