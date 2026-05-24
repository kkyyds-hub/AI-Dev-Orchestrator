# BCG-16A Apply-local + Local Git Commit Live Evidence

> 文档日期: 2026-05-24
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg16a_apply_local_git_commit_live.py

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| project_id | 358be915-a785-4c83-af21-318b8cf71f8d |
| batch_id | 4a65224b-1969-40ef-81d3-c5e94a23af02 |
| commit_candidate_id | c9eee8a2-e127-49a9-b4bc-83291955ea75 |
| isolated_repo_root | E:\bcg16a-workspaces\bcg16a-isolated-repo |
| isolated repo outside main repo | Yes |

---

## 2. Guard Chain

Full chain verified before apply-local:

| Step | Result |
|---|---|
| Project creation | 201 |
| Workspace binding (isolated repo) | OK |
| Snapshot refresh | OK |
| Tasks (Project Director) | 4 tasks |
| Deliverable | 201 |
| Change plans (2, distinct tasks) | 201 |
| Change batch | OK |
| Preflight (empty commands) | ready_for_execution |
| Verification run (passed) | 201 |
| Commit candidate (draft) | OK |
| Release gate approve | qualification_established=True |

---

## 3. Apply-local Success

- **API**: `POST /repositories/change-batches/{id}/apply-local`
- **Files**: README.md (modified), NEW_FILE.md (added)
- **status**: applied
- **verification_passed**: true
- **error_category**: null
- **error_summary**: null
- **rollback_performed**: false
- **log_path**: non-empty
- **diff_summary**: README.md in modified_files, NEW_FILE.md in added_files
- **Workspace files on disk**: README.md updated, NEW_FILE.md created
- **Main repo**: untouched

---

## 4. Git Commit Success

- **API**: `POST /repositories/change-batches/{id}/git-commit`
- **status**: committed
- **commit_sha**: 70e54bc8bd9a... (non-empty, not "unknown")
- **branch_name**: main
- **changed_files**: README.md, NEW_FILE.md (matches apply-local)
- **git log**: commit visible in `git log --oneline`
- **staged after commit**: clean (`git diff --cached --name-only` empty)
- **no remote configured**: `git remote -v` empty — no push possible
- **git_write_actions_triggered**: true (read from release gate)

---

## 5. Protection Paths

| Test | Expected error_category | Actual | Result |
|---|---|---|---|
| ../outside.txt | path_traversal | path_traversal | Pass |
| .git/config | git_internal_path | git_internal_path | Pass |
| Absolute path | path_traversal | path_traversal | Pass |

---

## 6. No-Push / No-PR / No-Merge Boundary

- No `git push` called
- No remote configured (`git remote -v` empty)
- No PR creation API called
- No merge API called
- BCG-17 (remote push / PR / merge) remains Deferred

---

## 7. Runtime Evidence Gap Assessment

None.

---

## 8. Uncovered Scope

- Gate not approved protection path (could not construct failing scenario — gate was approved directly)
- Preflight not passed protection path (batch was ready_for_execution)
- Commit candidate missing protection path (candidate was created)
- Apply before commit protection path (commit succeeds after apply)
- Apply verification failed then commit blocked (verification passed)
- Unrelated staged files leaking into commit (verified by git reset + staged validation in service)

---

## 9. Gate Conclusion

```text
BCG-16 Runtime Evidence: Pass
  - Apply-local success (write + verify): Pass
  - Git-commit success (stage only changed_files, local commit): Pass
  - Path safety (../, .git, absolute): Pass
  - No push / no PR / no merge: Pass
  - Main repo untouched: Pass

BCG-16 Runtime Evidence Pass.

AI Project Director total closure remains Partial. Do not mark total closure Pass.
```

---

## 10. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg16a_apply_local_git_commit_live.py
```

Result: **55 passed, 0 failed, 0 Runtime Evidence Gaps**
