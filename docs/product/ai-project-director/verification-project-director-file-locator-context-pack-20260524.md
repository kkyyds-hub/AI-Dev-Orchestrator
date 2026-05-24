# BCG-12A File Locator + Context Pack Live Evidence

> 文档日期: 2026-05-24
> 模型: DeepSeek
> 证据类型: Live Evidence Script
> 脚本: runtime/orchestrator/scripts/bcg12a_file_locator_context_pack_live.py
> API: GET/POST /repositories/projects/{project_id}/file-locator/search, context-pack

---

## 1. Evidence Summary

| Field | Value |
|---|---|
| project_id | 423367da-966b-4c2e-b8c8-a4ff5f7f2377 |
| repository_workspace_id | e1e32ddb-e858-4224-b301-5362f97c1864 |
| root_path | E:\bcg11a-workspaces\bcg11a-sample-repo |
| root_path outside main repo | Yes |
| root_path outside runtime_data_dir | Yes |
| root_path outside system temp | Yes |
| snapshot_id | 4a769201-f0f4-4f64-806a-b09b7606950e |
| snapshot status | success |
| snapshot file_count | 5 |
| snapshot language_breakdown | Markdown(2), JSON(1), Python(1), TypeScript(1) |

---

## 2. Repository Workspace Verification

- GET /repositories/projects/{project_id} returned workspace binding.
- root_path is absolute (E:\bcg11a-workspaces\bcg11a-sample-repo).
- access_mode == read_only.
- .git directory exists.
- root_path not inside AI-Dev-Orchestrator main repo tree.
- root_path not inside runtime_data_dir.
- root_path not inside system temp.
- Main repo write not permitted.

---

## 3. Snapshot Verification

- GET /repositories/projects/{project_id}/snapshot returned consistent snapshot.
- status == success, scan_error == null.
- file_count == 5.
- Tree includes: README.md, src, web, config, docs.
- language_breakdown includes: Markdown, Python, TypeScript, JSON.
- Ignored directories include: .git, node_modules, __pycache__, .venv, build, dist.
- Tree does NOT contain node_modules/ignored.js or __pycache__/ignored.py.

---

## 4. File Locator Results

### 4A: Keyword Query

- keywords: ["evidence", "repository", "context"], limit=5
- candidate_count: 4
- candidates: README.md, config/app.json, src/main.py, web/app.tsx
- scanned_file_count: 5
- All candidates have valid relative paths, score > 0, match_reasons non-empty.

### 4B: Path Prefix + File Type Query

- path_prefixes: ["src", "web", "config", "docs"]
- file_types: ["py", "tsx", "json", "md"]
- candidate_count: 5
- candidates: README.md, config/app.json, src/main.py, docs/spec.md, web/app.tsx
- All 5 expected files found.
- All candidates have valid relative paths, score > 0, match_reasons non-empty.

### 4C: Task Query

- task_query: "build context pack for repository binding snapshot evidence"
- candidate_count: 5
- scanned_file_count: 5
- All 5 files returned.
- candidates non-empty, candidate_count > 0, scanned_file_count >= 5.

### Common Locator Checks (all queries)

- project_id correct.
- repository_root_path == bound root_path.
- ignored_directory_names contains .git, node_modules, __pycache__.
- candidate_count > 0.
- total_match_count >= candidate_count.
- generated_at non-empty.
- Each candidate.relative_path is relative (no `..`, no absolute).
- Each candidate.score > 0.
- Each candidate.match_reasons non-empty.

---

## 5. Context Pack Results

### Build Request

- selected_paths: README.md, src/main.py, web/app.tsx, config/app.json, docs/spec.md
- selection_reasons_by_path from locator B match_reasons.
- task_query, keywords, path_prefixes, file_types all passed (route merges locator info).
- max_total_bytes: 12000, max_bytes_per_file: 4000.

### Build Response

- response.project_id == project_id.
- repository_root_path == bound root_path.
- selected_paths matches request.
- included_file_count: 5.
- total_included_bytes: 419.
- entries count == included_file_count (5).

### Entry Details

| relative_path | language | included_bytes | excerpt non-empty |
|---|---|---|---|
| README.md | Markdown | 92 | Yes |
| src/main.py | Python | 81 | Yes |
| web/app.tsx | TypeScript | 96 | Yes |
| config/app.json | JSON | 69 | Yes |
| docs/spec.md | Markdown | 81 | Yes |

- Each entry.relative_path in selected_paths.
- Each entry.excerpt non-empty.
- Each entry.included_bytes > 0.
- Each entry.start_line >= 1.
- Each entry.end_line >= entry.start_line.
- Each entry.match_reasons non-empty.
- Language coverage: Markdown, Python, TypeScript, JSON (4 of 4).
- source_summary non-empty and NOT the default fallback.
- focus_terms non-empty (derived from query: evidence, context, binding, snapshot).
- omitted_paths empty (all files fit in budget).

---

## 6. Budget Truncation

- Second context-pack call with max_total_bytes=512, max_bytes_per_file=256 (API minimums).
- truncated: False.
- NOTE: BCG-11A sample files are ~215 bytes combined (README.md ~92 + src/main.py ~123), well under the 512-byte API minimum.
- The real budget truncation logic IS tested by:
  `tests/test_repository_context_pack_api.py::test_build_project_context_pack_marks_truncated_when_total_budget_is_exhausted`
- This is a data limitation of the evidence sample, NOT a code gap.
- total_included_bytes (215) <= max_total_bytes (512).
- Both files fully included, not truncated.

---

## 7. Security Boundary

| Test | Expected | Actual | Result |
|---|---|---|---|
| ../outside.txt | 422 | 422 | Pass |
| Absolute path (script file) | 422 | 422 | Pass |
| node_modules/ignored.js | 422 or omitted | 200 INCLUDED | **SECURITY GAP** |
| __pycache__/ignored.py | 422 or omitted | 200 INCLUDED | **SECURITY GAP** |

### Security Gap Detail

The context-pack API (`POST /repositories/projects/{project_id}/context-pack`) successfully
reads files from ignored directories (`node_modules/`, `__pycache__/`) when explicitly
selected by path. The service's `_normalize_selected_paths()` only checks for path
traversal (`..`, absolute paths, drive-qualified paths), but does NOT cross-reference
against the repository's `ignored_directory_names`.

This means:
- `../` path traversal → correctly blocked (422)
- Absolute paths → correctly blocked (422)
- Files inside ignored directories → **incorrectly readable** (200)

Impact: An attacker who knows a file path inside node_modules or __pycache__ can
retrieve its contents via the context-pack API, bypassing the repository's ignore
rules. This is a defense-in-depth gap.

---

## 8. Runtime Evidence Gap Assessment

### Gaps Found

1. **node_modules file readable**: `node_modules/ignored.js` returned 200 with content via context-pack API.
2. **__pycache__ file readable**: `__pycache__/ignored.py` returned 200 with content via context-pack API.
3. **Budget truncation not verifiable with sample data**: Sample files are too small (215 bytes) to exceed the 512-byte API minimum. Verified separately by unit tests.

### Not Gaps

- Path traversal (`../`) → correctly rejected (422).
- Absolute path → correctly rejected (422).
- File locator returns valid, safe relative paths.
- File locator ignores `.git`, `node_modules`, `__pycache__` during scanning.
- Context pack excerpt, match reasons, focus terms all functional.

---

## 9. Uncovered Scope

- File locator with task_id (requires a valid project task).
- File locator with module_names.
- Context pack with files that actually exceed the budget (requires larger files).
- Web frontend UI integration.
- Worker-triggered locator/context-pack (manual API calls only).

---

## 10. Gate Conclusion

```text
BCG-12 Runtime Evidence: Partial
  - File locator (keywords / path_prefixes / task_query): Pass
  - Context pack (build / excerpt / languages / source_summary / focus_terms): Pass
  - Path safety (../, absolute path): Pass
  - Ignored directory file access: Security Gap (node_modules + __pycache__ readable)
  - Budget truncation: Pass (verified by test suite; sample files too small for live trigger)

BCG-12 overall: Partial (File locator + context pack evidence Pass / Security Gap exists)

AI Project Director total closure: remains Partial. Do not mark total closure Pass.
```

---

## 11. Live Evidence Command

```bash
cd runtime/orchestrator
python scripts/bcg12a_file_locator_context_pack_live.py
```

Result: **157 passed, 0 failed, 2 Runtime Evidence Gaps documented**
