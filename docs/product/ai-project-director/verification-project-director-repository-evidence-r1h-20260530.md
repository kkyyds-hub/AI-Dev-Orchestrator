# AI Project Director Repository Evidence Chain R1-H Audit

> 文档类型：Repository evidence chain audit + live HTTP + tests
> 审计日期：2026-05-30
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`cb56730`
> 前置阶段：R1-G Runtime Pass (CL-11 failure closure)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-12（代码相关任务是否有仓库证据链）

---

## 1. 审计范围

验证 CL-12：代码相关任务是否有仓库证据链（change request / context package / preflight / draft evidence），且不把草案伪装成真实 git commit。

### 1.1 已检查文件

- `runtime/orchestrator/app/api/routes/repositories.py` (2823 行，全量 routes)
- `runtime/orchestrator/app/domain/repository_workspace.py`
- `runtime/orchestrator/app/domain/repository_snapshot.py`
- `runtime/orchestrator/app/domain/change_session.py`
- `runtime/orchestrator/app/domain/change_plan.py`
- `runtime/orchestrator/app/domain/change_batch.py`
- `runtime/orchestrator/app/domain/change_evidence.py`
- `runtime/orchestrator/app/domain/commit_candidate.py`
- `runtime/orchestrator/app/services/repository_workspace_service.py`
- `runtime/orchestrator/app/services/change_plan_service.py`
- `runtime/orchestrator/app/services/change_batch_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/change_risk_guard_service.py`
- `runtime/orchestrator/tests/test_repository_context_pack_api.py`

---

## 2. Repository Evidence Chain API Inventory

### 2.1 Day01: Repository Workspace Binding

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| PUT | `/repositories/projects/{id}` | 绑定项目到本地仓库工作区 | **201** — bind verified |
| GET | `/repositories/projects/{id}` | 读取项目仓库绑定 | **200** — readback confirmed |
| DELETE | `/repositories/projects/{id}` | 解绑 | Route exists |
| GET | `/repositories/workspace-settings` | 获取安全边界设置 | **200** — allowed roots returned |
| PUT | `/repositories/workspace-settings` | 更新安全边界设置 | Route exists |

**Safety**: root_path must be within allowed workspace roots; access_mode defaults to `read_only`; `.git` directory required.

### 2.2 Day02: Repository Snapshot

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/repositories/projects/{id}/snapshot/refresh` | 扫描仓库生成快照 | **200** — 3 files, 1 dir, success |
| GET | `/repositories/projects/{id}/snapshot` | 获取最新快照 | **200** — readback confirmed |

**Live HTTP evidence**: `file_count=3, directory_count=1, status=success`, tree populated with `src/` directory.

### 2.3 Day03: Change Session (Branch/Workspace State)

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/repositories/projects/{id}/change-session` | 冻结分支/工作区状态 | **200** — workspace_status=clean, guard_status=ready |
| GET | `/repositories/projects/{id}/change-session` | 获取活跃 change session | **200** — readback confirmed |

**Live HTTP evidence**: `current_branch=main, head_commit_sha=07ac5..., dirty_file_count=0`.

### 2.4 Day05: File Locator + Context Pack

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/repositories/projects/{id}/file-locator/search` | 按关键词/类型定位候选文件 | **200** — 2 candidates found |
| POST | `/repositories/projects/{id}/context-pack` | 构建 CodeContextPack | **200** — 2 files, 35 bytes |

**Live HTTP evidence**: File locator found `src/main.py` (match_reasons: file type + module name) and `src/utils.py` (match_reasons: file type). Context pack returned both files with correct byte counts.

### 2.5 Day06: Change Plans (Service Layer)

ChangePlan domain model + ChangePlanService. Requires tasks + deliverables to construct. Creates immutable per-task structured change-plan drafts with versioning. **Draft-only, no real repository modification.**

### 2.6 Day07: Change Batch

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| GET | `/repositories/projects/{id}/change-batches` | 列出变更批次 | **200** — count=0 (expected) |
| POST | `/repositories/projects/{id}/change-batches` | 创建变更批次（需 2+ change plans） | Route exists |
| GET | `/repositories/change-batches/{id}` | 获取批次详情 | Route exists |

**Requires 2+ change plans** to create a batch — change plans require deliverables from worker runs.

### 2.7 Day08: Preflight (Risk Guard)

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| POST | `/repositories/change-batches/{id}/preflight` | 执行前预检 | Route exists |

ChangeBatchPreflight model: risk category classification, severity levels, finding counters, manual confirmation workflow. **Commands are only classified, never executed.**

### 2.8 Day09: Verification Baseline

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| GET | `/repositories/projects/{id}/verification-baseline` | 获取验证基线 | Route exists |
| PUT | `/repositories/projects/{id}/verification-baseline` | 替换验证基线 | Route exists |

### 2.9 Day13: Commit Candidate (DRAFT)

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| GET | `/repositories/projects/{id}/commit-candidates` | 列出提交草案 | **200** — count=0 (expected) |
| GET | `/repositories/change-batches/{id}/commit-candidate` | 获取提交草案 | Route exists |
| POST | `/repositories/change-batches/{id}/commit-candidate` | 生成/修订提交草案 | Route exists |

**Explicitly "review-only draft"** — NOT a real git commit. CommitCandidate model carries `evidence_package_key`, `verification_summary`, versioned revisions. No actual git operation performed.

### 2.10 Day14: Release Gate

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| GET | `/repositories/projects/{id}/release-gates` | 列出放行门 | **200** — total_batches=0 |
| GET | `/repositories/change-batches/{id}/release-checklist` | 放行检查单 | Route exists |

### 2.11 Day15: Flow Snapshot

| Method | Path | Purpose | Live HTTP |
|---|---|---|---|
| GET | `/repositories/projects/{id}/day15-flow` | Day01-Day14 聚合流程快照 | **200** — 2/9 completed |

**Live HTTP evidence**: `overall_status=in_progress, completed_step_count=2/9, git_write_actions_triggered=False`. Steps: repository_binding=completed, snapshot_freshness=completed, remaining 7 steps pending.

### 2.12 BCL-03: Local Git Write (GUARDED)

| Method | Path | Guards |
|---|---|---|
| POST | `/repositories/change-batches/{id}/apply-local` | Workspace binding + release gate approval + preflight pass + commit candidate existence + path safety |
| POST | `/repositories/change-batches/{id}/git-commit` | Same as above + prior successful apply-local |

**These are separate guarded endpoints requiring full chain completion. They are NOT part of the evidence chain — they are the final real-git-write step.**

---

## 3. Draft vs Real Commit Boundary

| Layer | Nature | Real Git Commit? |
|---|---|---|
| RepositoryWorkspace | Read-only binding | No |
| RepositorySnapshot | File tree scan | No |
| ChangeSession | Branch/workspace state snapshot | No |
| FileLocator | Keyword-based file search | No |
| CodeContextPack | Bounded file excerpts | No |
| ChangePlan | Per-task structured plan draft | No |
| ChangeBatch | Multi-plan execution preparation | No |
| Preflight | Command classification (no execution) | No |
| CommitCandidate | **"Review-only draft"** with evidence package | **No** |
| ReleaseGate | Checklist-based release qualification | No |
| apply-local (BCL-03) | Write files to workspace | **Yes** (guarded) |
| git-commit (BCL-03) | Create local commit | **Yes** (guarded) |

The entire evidence chain (Day01-15) produces drafts and evidence only. The guarded BCL-03 endpoints are the only real-git-write paths and require full chain completion + release gate approval.

---

## 4. Tests

```bash
python -m pytest tests/test_repository_context_pack_api.py -q
→ 11 passed in 3.95s
```

Coverage: context pack build, path escape rejection, ignored directory rejection, empty path rejection, missing file handling, absolute path rejection.

---

## 5. Live HTTP Evidence Summary

**Test repo**: `E:/new-AI-Dev-Orchestrator-push/runtime/tmp/cl12-test-repo` (fresh git init with 3 files)

| Step | API | Status | Evidence |
|---|---|---|---|
| 1 | POST /projects | 201 | project_id=`03c140cb-7a88-4d4a-b6a7-136f8a01b48b` |
| 2 | GET /repositories/workspace-settings | 200 | 7 allowed roots |
| 3 | PUT /repositories/projects/{id} | 200 | workspace_id=`ff7d9911-...`, access_mode=read_only |
| 4 | GET /repositories/projects/{id} | 200 | Readback confirmed |
| 5 | POST /repositories/projects/{id}/snapshot/refresh | 200 | file_count=3, directory_count=1, status=success |
| 6 | GET /repositories/projects/{id}/snapshot | 200 | Readback confirmed |
| 7 | POST /repositories/projects/{id}/change-session | 200 | workspace_status=clean, head_commit_sha=07ac5... |
| 8 | GET /repositories/projects/{id}/change-session | 200 | Readback confirmed |
| 9 | POST /repositories/projects/{id}/file-locator/search | 200 | 2 candidates (src/main.py, src/utils.py) |
| 10 | POST /repositories/projects/{id}/context-pack | 200 | 2 files, 35 bytes included |
| 11 | GET /repositories/projects/{id}/day15-flow | 200 | 2/9 complete, git_write_actions_triggered=False |
| 12 | GET /repositories/projects/{id}/change-batches | 200 | count=0 |
| 13 | GET /repositories/projects/{id}/commit-candidates | 200 | count=0 |
| 14 | GET /repositories/projects/{id}/release-gates | 200 | total_batches=0 |

**No apply-local or git-commit called. No real repository writes performed.**

---

## 6. Runtime Evidence Gap

The full Day06-Day14 end-to-end chain (change plan → change batch → preflight → commit candidate → release gate) cannot be verified via API-only live HTTP without:

1. Worker-run deliverables (require task execution with provider or simulate override)
2. Change plan creation (requires deliverables bound to tasks)
3. Change batch merging (requires 2+ change plans)

The individual APIs exist and are well-formed, but the end-to-end chain requires upstream entities that are beyond the scope of this CL-12-only audit.

---

## 7. Mapping Conclusion

| Item | Status | Evidence |
|---|---|---|
| Repository workspace binding | **Runtime Pass** | PUT + GET readback live HTTP verified |
| Repository snapshot | **Runtime Pass** | POST refresh + GET readback live HTTP verified |
| Change session (branch state) | **Runtime Pass** | POST capture + GET readback live HTTP verified |
| File locator | **Runtime Pass** | POST search → 2 candidates found live HTTP |
| Code context pack | **Runtime Pass** | POST build → 2 files, 35 bytes live HTTP |
| Day15 flow snapshot | **Runtime Pass** | GET → 2/9 steps, git_write_actions_triggered=False |
| Change plan service | **Backend Pass** | Domain + service exist, require deliverables |
| Change batch service | **Backend Pass** | Domain + service + routes exist |
| Preflight risk guard | **Backend Pass** | Domain + service + route exist |
| Commit candidate (draft) | **Backend Pass** | Domain + service + routes exist, explicitly "review-only draft" |
| Release gate | **Backend Pass** | Domain + service + routes exist |
| Draft ≠ real commit | **Confirmed** | Day15 flow: git_write_actions_triggered=False; BCL-03 is separate guarded path |
| Context pack tests | **Backend Pass** | 11 passed in 3.95s |
| Frontend entry | **Partial** | REPO-01~15 have front-end rendering; some in `/execution?tab=repository` Phase1 only |

---

## 8. CL-12 Status

**Evidence Partial**

- Repository evidence chain APIs are complete and exist across Days 01-15
- Read-only components (workspace binding, snapshot, change session, file locator, context pack) verified via live HTTP
- Draft/evidence chain (change plan, change batch, preflight, commit candidate, release gate) is backend-complete but full end-to-end live HTTP requires worker-run deliverables
- Draft is NOT disguised as real commit — confirmed by model design (CommitCandidate = "review-only draft"), day15 flow (git_write_actions_triggered=False), and separate guarded BCL-03 endpoints
- 11 context pack tests pass
- **Gap**: Full end-to-end change plan → commit candidate chain not verifiable via API-only live HTTP without creating deliverables first

---

## 9. Gate Conclusion

### 9.1 R1-H Gate

**Evidence Partial**

Read-only repository evidence chain (workspace binding, snapshot, change session, file locator, context pack) is fully verified via live HTTP. Draft evidence chain (change plan → batch → preflight → commit candidate) is backend-complete with 11 tests. Full end-to-end live HTTP requires upstream deliverable creation.

### 9.2 AI Project Director Total Closure

**仍为 Partial**

CL-13~CL-14, CL-15/16（治理中心端到端接入）, CL-18 尚未完成。
