# BCG-11A Repository Binding & Snapshot Live Evidence

> Document date: 2026-05-24
> Repository path: `docs/product/ai-project-director/verification-project-director-repository-binding-snapshot-20260524.md`
> Phase: BCG-11A (R1 hardened) — Repository Binding & Snapshot Live Evidence

---

## 1. Summary

BCG-11A-R1 live evidence confirms that a project can be bound to a real local Git repository through the workspace-settings safety boundary, and the system can generate a structured snapshot (tree, language stats, file counts, ignore rules) and serve it through existing read APIs.

R1 hardening fixes:
- Sample repo moved outside the AI-Dev-Orchestrator main repo tree.
- Allowed roots preserved (old + new), not overwritten.
- Real out-of-bounds existing Git repo rejection test added.
- Language breakdown assertions strengthened (all 4 languages verified).
- Location assertions confirm sample is outside main repo, runtime_data_dir, system temp.

---

## 2. Evidence IDs

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| sample_repo_root | `E:\bcg11a-workspaces\bcg11a-sample-repo` |
| sample_repo_outside_main_repo | True (verified) |
| allowed_workspace_root | `E:\bcg11a-workspaces` |
| oob_repo_root | `E:\bcg11a-oob\bcg11a-oob-repo` |
| workspace_id | `e1e32ddb-e858-4224-b301-5362f97c1864` |
| snapshot_id | `4a769201-f0f4-4f64-806a-b09b7606950e` |

---

## 3. Sample Repository Structure

A dedicated BCG-11A Git repo was created at `E:\bcg11a-workspaces\bcg11a-sample-repo`, outside the AI-Dev-Orchestrator main repo tree:

```
E:\bcg11a-workspaces\bcg11a-sample-repo\
  .git/
  README.md
  src/main.py
  web/app.tsx
  config/app.json
  docs/spec.md
  __pycache__/ignored.py       (should be ignored)
  node_modules/ignored.js      (should be ignored)
```

An out-of-bounds Git repo was created at `E:\bcg11a-oob\bcg11a-oob-repo` (NOT under the allowed root), used to verify safety boundary rejection.

---

## 4. Workspace Settings (R1: Preserve + Append)

| Field | Value |
|---|---|
| old_allowed_roots | `['E:\\new-AI-Dev-Orchestrator-push\\runtime\\tmp', 'E:\\bcg11a-workspaces']` |
| effective_allowed_roots | `['E:\\new-AI-Dev-Orchestrator-push\\runtime\\tmp', 'E:\\bcg11a-workspaces']` |
| preserved_existing_allowed_roots | true |
| sample_allowed_root_added | true |

R1 fix: Allow root list is built as `old_roots + [sample_parent]` (deduplicated), not `[sample_parent]` alone. Existing user-configured roots are preserved.

---

## 5. Safety Boundary Verification (R1: 4 categories)

| # | Test | Expected | Result |
|---|---|---|---|
| 1 | Bind non-existent path | 422 | Pass |
| 2 | Bind non-Git directory (under allowed root) | 422 | Pass |
| 3 | Bind out-of-bounds existing Git repo | 422 | Pass |
| 4 | Bind valid Git repo (under allowed root) | 200 | Pass |

**Test 3 (R1 new):** `E:\bcg11a-oob\bcg11a-oob-repo` is an existing Git repo with `.git`, but its parent `E:\bcg11a-oob` is NOT in the allowed roots list. The API correctly returns 422 with detail text confirming the root "exceeds the configured allowed workspace roots".

---

## 6. Bind API Request/Response

### Request
```json
{
  "root_path": "E:\\bcg11a-workspaces\\bcg11a-sample-repo",
  "display_name": "BCG-11A Evidence Repo",
  "access_mode": "read_only",
  "default_base_branch": "main",
  "ignore_rule_summary": [".git", "node_modules", "__pycache__"]
}
```

### Response Key Fields
| Field | Value |
|---|---|
| id | `e1e32ddb-e858-4224-b301-5362f97c1864` |
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| root_path | `E:\bcg11a-workspaces\bcg11a-sample-repo` |
| display_name | `BCG-11A Evidence Repo` |
| access_mode | `read_only` |
| default_base_branch | `main` |

### GET Read-back: All fields match. Pass.

---

## 7. Snapshot Refresh Response

| Field | Value |
|---|---|
| id | `4a769201-f0f4-4f64-806a-b09b7606950e` |
| status | `success` |
| scan_error | `null` |
| file_count | `5` |
| directory_count | `4` |
| repository_root_path | `E:\bcg11a-workspaces\bcg11a-sample-repo` |
| scanned_at | Non-null |
| created_at | Non-null |
| updated_at | Non-null |

### Language Breakdown (R1: strengthened)
| Language | Count | Assertion |
|---|---|---|
| Markdown | 2 | >= 2 |
| JSON | 1 | >= 1 |
| Python | 1 | >= 1 |
| TypeScript | 1 | >= 1 |

### Tree Structure
| Name | Kind |
|---|---|
| config | directory |
| docs | directory |
| README.md | file |
| src | directory |
| web | directory |

### Ignored Directories
`.git`, `.venv`, `__pycache__`, `node_modules`, `dist`, `build`

- `node_modules/ignored.js` — correctly excluded from tree
- `__pycache__/ignored.py` — correctly excluded from tree
- `.git` — correctly excluded

### GET /repositories/projects/{project_id}/snapshot Read-back
- snapshot_id matches refresh result
- file_count matches refresh result
- directory_count matches refresh result
- language_breakdown matches
- tree matches
- All fields consistent between POST refresh and GET read-back.

---

## 8. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | `/repositories/workspace-settings` | Read allowed roots |
| PUT | `/repositories/workspace-settings` | Configure allowed roots (preserve + append) |
| PUT | `/repositories/projects/{project_id}` | Bind repository (valid + 3× boundary tests) |
| GET | `/repositories/projects/{project_id}` | Read bound workspace |
| POST | `/repositories/projects/{project_id}/snapshot/refresh` | Refresh snapshot |
| GET | `/repositories/projects/{project_id}/snapshot` | Read latest snapshot |

---

## 9. Live Evidence Command & Result (R1)

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe scripts\bcg11a_repository_binding_snapshot_live.py
```

**Result: 71 passed, 0 failed.**

---

## 10. Regression Test Command & Result

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q
```

**Result: 132 passed, 3 warnings in 32.96s.**

---

## 11. R1 Fixes Summary

| Fix | Before (BCG-11A) | After (BCG-11A-R1) |
|---|---|---|
| Sample repo location | `runtime/tmp/bcg11a-sample-repo` (inside repo tree) | `E:\bcg11a-workspaces\bcg11a-sample-repo` (outside repo tree) |
| Allowed roots handling | Overwritten to `[sample_parent]` | Old roots preserved, new root appended and deduplicated |
| Out-of-bounds test | Non-existent path + non-Git dir only | Added existing Git repo outside allowed root → 422 |
| Language assertions | `"Markdown" in langs or len >= 1` | `Markdown>=2`, `Python>=1`, `TypeScript>=1`, `JSON>=1` each checked independently |
| Location assertions | None | Verified outside main repo, runtime_data_dir, system temp |

---

## 12. Uncovered Scope

| Item | Status | Reason |
|---|---|---|
| BCG-12 (file locator / context pack) | Not covered | Out of BCG-11A scope |
| BCG-13 (change plan / change batch) | Not covered | Out of BCG-11A scope |
| BCG-14 (preflight / manual confirmation) | Not covered | Out of BCG-11A scope |
| Release Gate (BCG-18) | Not covered | Out of BCG-11A scope |
| apply-local / git-commit | Not called | Strict boundary for BCG-11A |
| Project detail with repository_workspace | Optional | Project detail API not tested separately |
| AI Project Director total closure | Not covered | BCG-11A is one piece of total closure |

---

## 13. Gate Conclusion

**BCG-11A-R1 Repository Binding & Snapshot Evidence: Pass (71/71)**

- Safety boundary fully verified: non-existent path, non-Git dir, out-of-bounds existing Git repo all reject with 422.
- Allowed roots preserved (not overwritten) when adding new workspace root.
- Sample repo verified outside main repo tree, outside runtime_data_dir, outside system temp.
- Language breakdown with strengthened assertions for all 4 languages.
- Ignored directories (.git, node_modules, __pycache__) correctly exclude files from tree.
- Snapshot GET read-back consistent with POST refresh.
- BCG-11: Runtime Evidence Pass for repository binding / snapshot evidence.
- AI Project Director total closure remains Partial (BCG-12~30 still open).
