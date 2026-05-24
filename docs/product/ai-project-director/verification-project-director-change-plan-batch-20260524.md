# BCG-13A Change Plan → Change Batch Live Evidence

> 文档日期: 2026-05-24
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg13a_change_plan_batch_live.py

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| project_id | 423367da-966b-4c2e-b8c8-a4ff5f7f2377 |
| workspace_id | e1e32ddb-e858-4224-b301-5362f97c1864 |
| snapshot_id | 4a769201-f0f4-4f64-806a-b09b7606950e |
| task_id | db204e31-f244-4f9b-a469-abcc5e0b873f |
| deliverable_id | 3ae2a721-4396-453e-8d1b-529a50efb29c |
| run_id | 834b38aa-3669-4121-9424-3aa4999cad2e |
| change_plan_id | f220deae-ce87-4b34-8b85-faf06a802b3c |
| change_batch_id | 2d07dde6-0216-40ef-ae2b-b4959db58d33 |

---

## 2. BCG-12 Prerequisite Verification

All BCG-12 prerequisites re-verified:
- Workspace exists and matches BCG-11A binding.
- Snapshot status = success, file_count = 5.
- File locator returns 5 candidates.
- Context pack builds for 3+ legal files.
- Ignored directory paths (node_modules, __pycache__, .git) all return 422.

---

## 3. Change Plan v1

- API: `POST /planning/projects/{project_id}/change-plans` → 201
- change_plan_id: `f220deae-ce87-4b34-8b85-faf06a802b3c`
- version_number: 1
- title: "BCG-13A repository context change plan"
- task_id: db204e31-f244-4f9b-a469-abcc5e0b873f
- primary_deliverable_id: 3ae2a721-4396-453e-8d1b-529a50efb29c
- target_files: README.md, src/main.py, web/app.tsx, config/app.json (4 files)
- expected_actions: 3 items
- risk_notes: 2 items
- verification_commands: ["python -m pytest tests/test_repository_context_pack_api.py -q"]
- source_summary references BCG-12 file locator + context pack evidence
- focus_terms: repository, context, change, evidence, bcg13a

### v1 Assertions

- HTTP 201, project_id/task_id/primary_deliverable_id correct.
- current_version_number = 1, versions count 1.
- latest_version.version_number = 1.
- target_files >= 3, expected_actions non-empty, risk_notes non-empty, verification_commands non-empty.
- related_deliverables contains deliverable_id.
- All target_files from BCG-12 context pack selected_paths.
- No target_files in ignored directories.

---

## 4. Change Plan v2 (Revision)

- API: `POST /planning/change-plans/{change_plan_id}/versions` → 200
- version_number: 2
- target_files: README.md, src/main.py, web/app.tsx, config/app.json, docs/spec.md (5 files, +1 from v1)
- intent_summary: "BCG-13A v2 revision"
- source_summary: retains BCG-12 context pack basis
- focus_terms: repository, context, change, evidence, bcg13a, revision
- expected_actions: 3 items (updated)
- risk_notes: 2 items (updated — new docs/spec.md sync risk)
- related_deliverable_ids: contains 3ae2a721-4396-453e-8d1b-529a50efb29c

### v2 Assertions

- current_version_number = 2.
- versions count >= 2.
- latest_version.version_number = 2.
- v1 (version 1) and v2 (version 2) both present in versions array.
- v2.created_at non-null.

---

## 5. Change Plan Read-back

- `GET /planning/change-plans/{change_plan_id}` → 200, versions=2, status=draft.
- `GET /planning/projects/{project_id}/change-plans` → change_plan_id found in project list.
- `GET /planning/projects/{project_id}/change-plans?task_id={task_id}` → change_plan_id found; all plans have correct task_id.

---

## 6. Change Batch

### Second Change Plan

- The API requires ≥2 change plans with **distinct tasks** per batch.
- 4 tasks exist in the project (from BCG-04A plan version → task creation).
- A second change plan was created for task `eadbd502-9e85-4ba6-9d37-b79c80627a59`:
  - plan_id: `e2118411-5ea9-4e14-ad17-ef1167383d96`
  - same deliverable, same project, same BCG-12 context pack basis.
  - target_files: README.md, config/app.json, docs/spec.md
- This is BCG-13A evidence setup, not business logic.

### Batch Creation

- API: `POST /repositories/projects/{project_id}/change-batches` → 200
- change_batch_id: `2d07dde6-0216-40ef-ae2b-b4959db58d33`
- title: "BCG-13A execution preparation batch"
- status: preparing
- change_plan_count: 2
- task_count: 2
- target_file_count: 5
- overlap_file_count: 3
- verification_command_count: 1

### Batch Read-back

- `GET /repositories/projects/{project_id}/change-batches` → batch_id found in list (1 batch).
- `GET /repositories/change-batches/{change_batch_id}` → detail matches: 2 tasks, 5 target_files, 3 timeline entries.

---

## 7. Active Batch Conflict

No active batch conflict occurred. No prior active batch existed for this project.

---

## 8. Runtime Evidence Gap Assessment

### Gaps Found

None.

### Not Gaps

- Change plan v1 → 201, all target files from BCG-12 context pack.
- Change plan v2 → revision correctly appended, version_number=2.
- Read-back (detail, project list, task-filtered list) all consistent.
- Change batch created with 2 plans, 2 tasks, 5 target files.
- Batch read-back consistent with creation.
- No ignored directory paths in any target_file.
- No path traversal in any target_file.

---

## 9. Uncovered Scope

- Change plan with verification_template_ids (project has no templates configured).
- Change plan with context_pack_generated_at (BCG-12 context pack does not expose a timestamp in the response).
- Change batch with preflight / manual confirmation (BCG-14 scope).
- Change batch supersede / status transitions.
- Planning/apply integration.

---

## 10. Gate Conclusion

```text
BCG-13 Runtime Evidence: Pass for change plan / change batch evidence
  - Change plan v1 creation (201): Pass
  - Change plan v2 revision: Pass
  - Change plan read-back (detail/list/task-filtered): Pass
  - Change batch creation (2 plans, 2 tasks): Pass
  - Change batch read-back: Pass
  - Target files all from BCG-12 context pack: Pass
  - No ignored directory paths leaked: Pass

BCG-13 Runtime Evidence Pass.

AI Project Director total closure remains Partial. Do not mark total closure Pass.
```

---

## 11. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg13a_change_plan_batch_live.py
```

Result: **97 passed, 0 failed, 0 Runtime Evidence Gaps**
