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

- Frontend Entry Pending (BCG-16 backend Runtime Evidence Pass; frontend apply-local / git-commit entry not yet confirmed).
- BCG-17 remote push / PR / merge remains Deferred (not in BCG-16 scope).

All BCG-16 guard paths are now covered by live evidence (R2 code fix + R3/R4 verification).

---

## 9. BCG-16A-R2 Code Fix (2026-05-24)

Guard order in `LocalGitWriteService.apply_local()` and `git_commit()`
reordered from (gate → preflight → candidate) to (preflight → candidate → gate).
This ensures precise error categories: `preflight_not_passed` before
`commit_candidate_missing` before `gate_not_approved`.

Commit: `a7ee217`. Tests: `tests/test_apply_local_git_commit_guard.py` (6 tests).

---

## 10. BCG-16A-R3/R4 Guard Path Runtime Evidence (2026-05-24)

Script: `runtime/orchestrator/scripts/bcg16a_r3_apply_local_git_guard_live.py`

All 7 guard paths live-verified with hardening (main repo pollution check,
isolated repo HEAD before/after, no file writes, no commits, no remotes):

| # | Guard Path | error_category | Hardened |
|---|---|---|---|
| 1 | preflight not_started | preflight_not_passed | HEAD unchanged, no file write, no commit |
| 2 | preflight blocked | preflight_not_passed | HEAD unchanged, no file write, no commit |
| 3 | no commit candidate | commit_candidate_missing | HEAD unchanged, no file write, no commit |
| 4 | gate not approved | gate_not_approved | HEAD unchanged, no file write, no commit |
| 5 | git-commit before apply | apply_not_done | HEAD unchanged, no commit |
| 6 | verification failed | apply_verification_failed | HEAD unchanged, no commit |
| 7 | unrelated staged files | excluded from commit | Only changed_files in commit, staged clean |

Main repo: HEAD=737d407d unchanged, status clean after all 7 scenarios.

---

## 11. Gate Conclusion

```text
BCG-16 Runtime Evidence: Pass
  - Apply-local + git-commit success path: Pass
  - Path safety (../, .git, absolute): Pass
  - preflight_not_passed (not_started + blocked): Pass (R3/R4)
  - commit_candidate_missing: Pass (R3/R4)
  - gate_not_approved: Pass (R3/R4)
  - apply_not_done: Pass (R3/R4)
  - apply_verification_failed: Pass (R3/R4)
  - unrelated staged excluded: Pass (R3/R4)
  - Main repo untouched: Pass (R4 hardening)
  - No push / no PR / no merge: Pass

BCG-16: Backend Pass / Runtime Evidence Pass / Frontend Entry Pending.
BCG-17 remote push / PR / merge: Deferred.
AI Project Director total closure remains Partial.
```

---

## 12. Live Evidence Commands

```bash
# Success path
cd runtime/orchestrator
python scripts/bcg16a_apply_local_git_commit_live.py
# Result: 55/55 passed, 0 gaps

# Guard paths (hardened R4)
python scripts/bcg16a_r3_apply_local_git_guard_live.py
# Result: 224/224 passed, 0 gaps
```
