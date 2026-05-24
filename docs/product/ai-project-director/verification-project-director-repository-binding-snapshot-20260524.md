# BCG-11A Repository Binding & Snapshot Live Evidence

> Document date: 2026-05-24
> Repository path: `docs/product/ai-project-director/verification-project-director-repository-binding-snapshot-20260524.md`
> Phase: BCG-11A — Repository Binding & Snapshot Live Evidence

---

## 1. Summary

BCG-11A live evidence confirms that a project can be bound to a real local Git repository through the workspace-settings safety boundary, and the system can generate a structured snapshot (tree, language stats, file counts, ignore rules) and serve it through existing read APIs. All safety checks (out-of-bounds path, non-Git directory) correctly reject with 422.

---

## 2. Evidence IDs

| Field | Value |
|---|---|
| project_id | `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| sample_repo_root | `E:\new-AI-Dev-Orchestrator-push\runtime\tmp\bcg11a-sample-repo` |
| allowed_workspace_root | `E:\new-AI-Dev-Orchestrator-push\runtime\tmp` |
| workspace_id | `e1e32ddb-e858-4224-b301-5362f97c1864` |
| snapshot_id | `4a769201-f0f4-4f64-806a-b09b7606950e` |

---

## 3. Sample Repository Structure

A dedicated BCG-11A Git repo was created at `runtime/tmp/bcg11a-sample-repo`:

```
bcg11a-sample-repo/
  .git/
  README.md
  src/main.py
  web/app.tsx
  config/app.json
  docs/spec.md
  __pycache__/ignored.py       (should be ignored)
  node_modules/ignored.js      (should be ignored)
```

The directory `runtime/tmp/` is neither `runtime_data_dir` nor system temp, and is outside the AI-Dev-Orchestrator main repo. No git operations were performed on the main repository.

---

## 4. Safety Boundary Verification

| Test | API | Expected | Result |
|---|---|---|---|
| Read current settings | GET /repositories/workspace-settings | 200 with allowed roots | Pass |
| Update allowed roots | PUT /repositories/workspace-settings | 200, sample parent added | Pass |
| Re-read persistence | GET /repositories/workspace-settings | Sample parent in list | Pass |
| Bind non-existent path | PUT /repositories/projects/{id} | 422 | Pass |
| Bind non-Git directory | PUT /repositories/projects/{id} | 422 | Pass |
| Bind valid Git repo | PUT /repositories/projects/{id} | 200 | Pass |

---

## 5. Bind API Request/Response

### Request
```json
{
  "root_path": "E:\\new-AI-Dev-Orchestrator-push\\runtime\\tmp\\bcg11a-sample-repo",
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
| root_path | `E:\new-AI-Dev-Orchestrator-push\runtime\tmp\bcg11a-sample-repo` |
| display_name | `BCG-11A Evidence Repo` |
| access_mode | `read_only` |
| default_base_branch | `main` |

### GET Read-back: All fields match. Pass.

---

## 6. Snapshot Refresh Response

| Field | Value |
|---|---|
| id | `4a769201-f0f4-4f64-806a-b09b7606950e` |
| status | `success` |
| scan_error | `null` |
| file_count | `5` |
| directory_count | `4` |
| repository_root_path | `E:\new-AI-Dev-Orchestrator-push\runtime\tmp\bcg11a-sample-repo` |
| scanned_at | Non-null |
| created_at | Non-null |
| updated_at | Non-null |

### Language Breakdown
| Language | File Count |
|---|---|
| Markdown | 2 |
| JSON | 1 |
| Python | 1 |
| TypeScript | 1 |

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

## 7. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | `/repositories/workspace-settings` | Read allowed roots |
| PUT | `/repositories/workspace-settings` | Configure allowed roots |
| PUT | `/repositories/projects/{project_id}` | Bind repository (valid + boundary tests) |
| GET | `/repositories/projects/{project_id}` | Read bound workspace |
| POST | `/repositories/projects/{project_id}/snapshot/refresh` | Refresh snapshot |
| GET | `/repositories/projects/{project_id}/snapshot` | Read latest snapshot |

---

## 8. Live Evidence Command & Result

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe scripts\bcg11a_repository_binding_snapshot_live.py
```

**Result: 57 passed, 0 failed.**

---

## 9. Regression Test Command & Result

```bash
cd runtime/orchestrator
.\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q
```

**Result: 132 passed, 3 warnings in 33.61s.**

---

## 10. Uncovered Scope

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

## 11. Gate Conclusion

**BCG-11A Repository Binding & Snapshot Evidence: Pass (57/57)**

- Safety boundary (allowed roots, out-of-bounds, non-Git) verified.
- Repository binding via PUT /repositories/projects/{id} works with real Git repo.
- Snapshot refresh produces tree, language breakdown, file/directory counts.
- Ignore rules correctly exclude .git, node_modules, __pycache__ from tree.
- Snapshot GET read-back is consistent with POST refresh output.
- BCG-11: Runtime Evidence Pass for repository binding / snapshot evidence.
- AI Project Director total closure remains Partial (BCG-12~30 still open).
