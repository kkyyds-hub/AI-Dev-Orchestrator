# BCG-15A Commit Candidate Review-only Draft Live Evidence

> 文档日期: 2026-05-24
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg15a_commit_candidate_live.py

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| project_id | 423367da-966b-4c2e-b8c8-a4ff5f7f2377 |
| change_batch_id | 2d07dde6-0216-40ef-ae2b-b4959db58d33 |
| commit_candidate_id | 687909f0-b681-42a7-bd49-81832dc49b09 |
| evidence_package_key | cep-a001d0e5-65dd-55e7-b5ab-4518a31aaa06 |
| preflight status | manual_confirmed (ready_for_execution) |

---

## 2. APIs Used

| Method | Path | Purpose |
|---|---|---|
| GET | /repositories/change-batches/{id} | Verify preflight ready |
| POST | /runs/verification | Create passed verification run |
| POST | /repositories/change-batches/{id}/commit-candidate | Generate v1 draft |
| POST | /repositories/change-batches/{id}/commit-candidate | Generate v2 revision |
| GET | /repositories/change-batches/{id}/commit-candidate | Detail read-back |
| GET | /repositories/projects/{id}/commit-candidates | Project list read-back |

---

## 3. First Draft (v1)

- **API**: `POST /repositories/change-batches/{id}/commit-candidate`
- **Status**: draft
- **current_version_number**: 1
- **revision_count**: 1
- **latest_version.version_number**: 1
- **evidence_package_key**: cep-a001d0e5-65dd-55e7-b5ab-4518a31aaa06
- **message_title**: non-empty
- **message_body**: non-empty (contains review-only markers)
- **impact_scope**: non-empty
- **related_files**: non-empty
- **verification_summary**: total_runs=1, passed_runs=1, failed_runs=0
- **related_deliverables**: non-empty

---

## 4. Detail Read-back

- `GET /repositories/change-batches/{id}/commit-candidate` → 200
- candidate_id, change_batch_id, current_version_number, latest_version, versions all consistent with POST result.

---

## 5. Project List Read-back

- `GET /repositories/projects/{id}/commit-candidates` → 200
- Candidate found in list (1 total). current_version_number, status, change_batch_id consistent.

---

## 6. Second Revision (v2)

- **API**: `POST /repositories/change-batches/{id}/commit-candidate` (second call)
- **current_version_number**: 2
- **revision_count**: 2
- **versions**: v1 (version 1) and v2 (version 2) both present
- **latest_version.version_number**: 2
- **Custom fields**: message_title, message_body, impact_scope (3 items), related_files (5 files), revision_note all persisted
- **v1 preserved**: original message_title, evidence_package_key still present in versions array

---

## 7. Protection Paths

| Test | Expected | Actual | Result |
|---|---|---|---|
| Non-existent batch | 404 | 404 | Pass |
| Preflight manual_rejected batch | 409 | 409 | Pass |

The `POST /runs/verification` API was used to create a passed verification run (a prerequisite for commit-candidate generation). Without at least one passed run, the service correctly returns 409 "Verification evidence is missing."

---

## 8. Review-only Boundary

- **status**: draft (not committed, not merged)
- **No git write fields**: commit_sha, branch_name, push_status, merge_status not present in response
- **message_body**: Contains review/draft markers
- **No apply-local / git-commit / git-push called**

---

## 9. Runtime Evidence Gap Assessment

None.

---

## 10. Uncovered Scope

- Verification missing 409 (requires a batch with preflight ready but zero passed verification runs — the evidence setup creates a passed run, so this path is not tested live; the service logic is verified by code audit)
- Preflight not_started 409 (same as above)

---

## 11. Gate Conclusion

```text
BCG-15 Runtime Evidence: Pass
  - First draft v1: Pass
  - Detail read-back: Pass
  - Project list read-back: Pass
  - Second revision v2: Pass
  - Protection paths (404, 409 preflight): Pass
  - Review-only boundary: Pass

BCG-15 Runtime Evidence Pass.

AI Project Director total closure remains Partial. Do not mark total closure Pass.
```

---

## 12. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg15a_commit_candidate_live.py
```

Result: **68 passed, 0 failed, 0 Runtime Evidence Gaps**
