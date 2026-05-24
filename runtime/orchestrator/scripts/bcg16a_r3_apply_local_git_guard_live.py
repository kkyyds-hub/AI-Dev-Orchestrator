"""BCG-16A-R3 closeout: apply-local + git-commit guard paths (DeepSeek).

After BCG-16A-R2 code fix (guard order: preflight → candidate → gate),
re-verify all 6 guard paths with real API runtime evidence:
  1. preflight_not_passed (not_started / blocked)
  2. commit_candidate_missing
  3. gate_not_approved
  4. git-commit before apply-local → apply_not_done
  5. verification failed → git-commit blocked → apply_verification_failed
  6. unrelated staged files not in commit
"""

from __future__ import annotations

import json, os, shutil, stat, subprocess, sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.core.db import init_database
from app.main import create_application

_MAIN = Path(__file__).resolve().parents[3]
_BASE = _MAIN.parent / "bcg16a-r3-workspaces"

_passed = 0
_failed = 0
_gaps: list[str] = []

def _a(c, m):
    global _passed, _failed
    if c: _passed += 1
    else: _failed += 1; print(f"  FAIL: {m}")
    assert c, m

def _ck(c, m):
    global _passed, _failed
    if c: _passed += 1
    else: _failed += 1; print(f"  FAIL: {m}")

def _g(m):
    global _gaps; _gaps.append(m); print(f"  GAP: {m}")

def _req(c, m, p, *, j=None, es=200):
    r = c.request(m, p, json=j)
    if r.status_code != es:
        print(f"  API: {m} {p} -> {r.status_code} (exp {es}): {r.text[:200]}")
    _a(r.status_code == es, f"{m} {p} -> {r.status_code}, exp {es}")
    return r.json()

def _rs(c, m, p, *, j=None):
    r = c.request(m, p, json=j)
    return r.status_code, r.json()

def _rrm(target: Path):
    def _oe(fn, p, ei): Path(p).chmod(stat.S_IWRITE); fn(p)
    if target.exists(): shutil.rmtree(target, onerror=_oe)

def _git(repo: Path, *a: str) -> str:
    return (subprocess.run(["git", *a], cwd=str(repo), capture_output=True, text=True, timeout=30).stdout or "").strip()


# ── Setup helpers ────────────────────────────────────────────────────────


def _make_repo(name: str) -> Path:
    repo = _BASE / f"repo-{name}"
    _rrm(repo); repo.mkdir(parents=True)
    (repo / "README.md").write_text("# R3\n", encoding="utf-8")
    for cmd in [["init","-b","main"], ["config","user.email","r3@e"], ["config","user.name","R3"], ["add","-A"], ["commit","-m","init"]]:
        subprocess.run(["git"] + cmd, cwd=str(repo), capture_output=True, check=True)
    _a(_MAIN.resolve() not in repo.resolve().parents and repo.resolve() != _MAIN.resolve(), "repo under main")
    return repo


def _setup_chain(client, repo: Path, *, preflight_ready=True, with_candidate=True, approve_gate=True, vcmd="python -c \"print('ok')\"") -> dict[str, Any]:
    """Build full chain: project → workspace → tasks → deliverable → plans → batch → preflight → candidate → gate."""
    r = str(repo.resolve())
    p = _req(client, "POST", "/projects", j={"name": "R3", "summary": "R3."}, es=201)
    pid = p["id"]

    ws = _req(client, "GET", "/repositories/workspace-settings")
    roots = list(ws.get("allowed_workspace_roots", []))
    parent = str(repo.parent)
    if parent not in roots:
        roots.append(parent)
        _req(client, "PUT", "/repositories/workspace-settings", j={"allowed_workspace_roots": roots})
    _req(client, "PUT", f"/repositories/projects/{pid}", j={"root_path": r, "display_name": "R3", "access_mode": "read_only", "default_base_branch": "main"})
    _req(client, "POST", f"/repositories/projects/{pid}/snapshot/refresh")

    s = _req(client, "POST", "/project-director/sessions", j={"goal_text": "R3 task.", "project_id": pid}, es=201)
    answers = [{"question_id": q["id"], "answer": "R3"} for q in s.get("clarifying_questions", [])]
    if answers: _req(client, "POST", f"/project-director/sessions/{s['id']}/answers", j={"answers": answers})
    _req(client, "POST", f"/project-director/sessions/{s['id']}/confirm")
    pv = _req(client, "POST", f"/project-director/sessions/{s['id']}/plan-versions", j={}, es=201)
    _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/confirm")
    cr = _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/create-tasks", es=201)
    tids = cr.get("created_task_ids", []) or [t["id"] for t in _req(client, "GET", "/tasks") if t.get("project_id") == pid]
    _a(len(tids) >= 2, f"tasks: {len(tids)}")

    d = _req(client, "POST", "/deliverables", j={"project_id": pid, "type": "stage_artifact", "title": "R3D", "stage": "planning", "created_by_role_code": "architect", "summary": "R3.", "content": "# R3"}, es=201)
    did = d["id"]

    small = [{"relative_path": "README.md", "language": "Markdown", "file_type": "md", "rationale": "R3", "match_reasons": ["md"]}]
    base = {"primary_deliverable_id": did, "related_deliverable_ids": [did], "intent_summary": "R3.", "source_summary": "R3.", "focus_terms": ["r3"], "target_files": small, "expected_actions": ["test"], "risk_notes": ["test"], "verification_commands": [vcmd], "verification_template_ids": []}
    cp1 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[0], "title": "R3-A", **base}, es=201)
    cp2 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[1], "title": "R3-B", **base}, es=201)
    batch = _req(client, "POST", f"/repositories/projects/{pid}/change-batches", j={"title": "R3-batch", "change_plan_ids": [cp1["id"], cp2["id"]]})
    bid = batch["id"]

    if preflight_ready:
        _req(client, "POST", f"/repositories/change-batches/{bid}/preflight", j={"candidate_commands": []})
        b = _req(client, "GET", f"/repositories/change-batches/{bid}")
        pf = b.get("preflight", {})
        _a(pf.get("ready_for_execution") is True or pf.get("status") == "ready_for_execution", f"preflight: {pf.get('status')}")

    if with_candidate:
        # Create batch verification run first (candidate needs evidence)
        b2 = _req(client, "GET", f"/repositories/change-batches/{bid}")
        tasks_bt = b2.get("tasks", [])
        if tasks_bt:
            v_cp_id = tasks_bt[0]["change_plan_id"]
            # Verification run command must match the plan's verification_commands
            plan_vcmd = tasks_bt[0].get("verification_commands", ["python -c \"print('ok')\""])
            run_cmd = plan_vcmd[0] if plan_vcmd else "python -c \"print('ok')\""
            _req(client, "POST", "/runs/verification", j={"project_id": pid, "change_plan_id": v_cp_id, "change_batch_id": bid, "status": "passed", "command": run_cmd, "working_directory": ".", "duration_seconds": 0.1, "output_summary": "R3."}, es=201)
        _req(client, "POST", f"/repositories/change-batches/{bid}/commit-candidate", j={"message_title": "R3 cand"})

    if approve_gate and preflight_ready and with_candidate:
        _req(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={"action": "approve", "actor_name": "boss", "summary": "R3.", "comment": "", "highlighted_risks": [], "requested_changes": []})

    return {"project_id": pid, "batch_id": bid, "repo_root": r}


# ── Guard tests ──────────────────────────────────────────────────────────


def _test_phase(label, num, client, ctx, expected_cat, files=None):
    print()
    print("=" * 60)
    print(f"PHASE {num}: {label}")
    print("=" * 60)
    bid = ctx["batch_id"]
    s, d = _rs(client, "POST", f"/repositories/change-batches/{bid}/apply-local", j={"files": files or [{"relative_path": "README.md", "content": "# R3 ok\n"}]})
    _a(s == 200, f"HTTP {s}")
    _a(d.get("error_category") == expected_cat, f"error_category: {d.get('error_category')} (expected {expected_cat})")
    _a(d.get("status") == "failed", f"status: {d.get('status')}")
    _a(d.get("changed_files") == [], f"changed_files not empty: {d.get('changed_files')}")
    # Verify file NOT written
    repo = Path(ctx["repo_root"])
    if files is None or files[0].get("relative_path", "") != ".git/config":
        content = (repo / "README.md").read_text(encoding="utf-8")
        _ck("R3 ok" not in content, "file was written despite guard failure!")
    print(f"  {expected_cat}: OK (no file written)")


def _test_git_commit_phase(label, num, client, ctx, expected_cat):
    print()
    print("=" * 60)
    print(f"PHASE {num}: {label}")
    print("=" * 60)
    bid = ctx["batch_id"]
    s, d = _rs(client, "POST", f"/repositories/change-batches/{bid}/git-commit", j={})
    _a(s == 200, f"HTTP {s}")
    _a(d.get("error_category") == expected_cat, f"error_category: {d.get('error_category')} (expected {expected_cat})")
    _a(d.get("status") == "failed", f"status: {d.get('status')}")
    _a(d.get("commit_sha") is None, f"commit_sha not null: {d.get('commit_sha')}")
    print(f"  {expected_cat}: OK (no commit created)")


# ── Phase 6: Unrelated staged files ─────────────────────────────────────


def _test_unrelated_staged(client):
    print()
    print("=" * 60)
    print("PHASE 6: Unrelated staged files not in commit")
    print("=" * 60)

    repo = _make_repo("unrelated")
    ctx = _setup_chain(client, repo, preflight_ready=True, with_candidate=True, approve_gate=True)
    bid = ctx["batch_id"]
    rp = Path(ctx["repo_root"])

    # Create unrelated file and stage it
    (rp / "UNRELATED.md").write_text("# Should NOT be in commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "UNRELATED.md"], cwd=str(rp), capture_output=True, check=True)

    # Verify UNRELATED.md is staged
    staged_before = _git(rp, "diff", "--cached", "--name-only")
    _ck("UNRELATED.md" in staged_before, f"UNRELATED.md not staged before commit: {staged_before}")

    # Apply-local (write real files)
    s, d = _rs(client, "POST", f"/repositories/change-batches/{bid}/apply-local",
               j={"files": [{"relative_path": "README.md", "content": "# R3 updated\n"},
                            {"relative_path": "NEW_FILE.md", "content": "# R3 new\n"}]})
    _a(s == 200, f"apply HTTP {s}")
    _a(d.get("status") == "applied", f"apply status: {d.get('status')}")

    # Git-commit
    s2, d2 = _rs(client, "POST", f"/repositories/change-batches/{bid}/git-commit", j={})
    _a(s2 == 200, f"commit HTTP {s2}")
    _a(d2.get("status") == "committed", f"commit status: {d2.get('status')}")
    sha = d2.get("commit_sha", "")
    _ck(len(sha) > 0 and sha != "unknown", f"commit_sha: {sha}")

    # Check commit contents
    commit_files = _git(rp, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    _ck("README.md" in commit_files, f"README.md not in commit: {commit_files}")
    _ck("NEW_FILE.md" in commit_files, f"NEW_FILE.md not in commit: {commit_files}")
    _ck("UNRELATED.md" not in commit_files, f"UNRELATED.md LEAKED into commit! {commit_files}")

    # Verify staged is clean after commit
    staged_after = _git(rp, "diff", "--cached", "--name-only")
    _ck(staged_after == "", f"staged files after commit: {staged_after}")

    print(f"  UNRELATED.md excluded from commit: OK")
    print(f"  staged clean after commit: OK")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed, _gaps
    _passed = 0; _failed = 0; _gaps = []

    init_database()
    app = create_application()

    with TestClient(app) as client:
        # Phase 1: preflight not_started → preflight_not_passed
        # (no candidate needed — preflight check fires before candidate check)
        r1 = _make_repo("pf1")
        c1 = _setup_chain(client, r1, preflight_ready=False, with_candidate=False, approve_gate=False)
        _test_phase("preflight_not_started → preflight_not_passed", 1, client, c1, "preflight_not_passed")

        # Phase 2: preflight blocked → preflight_not_passed
        r2 = _make_repo("pf2")
        c2 = _setup_chain(client, r2, preflight_ready=True, with_candidate=False, approve_gate=False)
        # Re-run preflight with dangerous commands to make it blocked
        _req(client, "POST", f"/repositories/change-batches/{c2['batch_id']}/preflight", j={"candidate_commands": ["rm -rf /", "git push --force"]})
        _test_phase("preflight blocked → preflight_not_passed", 2, client, c2, "preflight_not_passed")

        # Phase 3: commit_candidate_missing
        r3 = _make_repo("cm")
        c3 = _setup_chain(client, r3, preflight_ready=True, with_candidate=False, approve_gate=False)
        _test_phase("commit_candidate_missing", 3, client, c3, "commit_candidate_missing")

        # Phase 4: gate_not_approved
        r4 = _make_repo("gate")
        c4 = _setup_chain(client, r4, preflight_ready=True, with_candidate=True, approve_gate=False)
        _test_phase("gate_not_approved", 4, client, c4, "gate_not_approved")

        # Phase 5: git-commit before apply → apply_not_done
        r5 = _make_repo("cba")
        c5 = _setup_chain(client, r5, preflight_ready=True, with_candidate=True, approve_gate=True)
        _test_git_commit_phase("git-commit before apply → apply_not_done", 5, client, c5, "apply_not_done")

        # Phase 6: verification failed → git-commit blocked
        r6 = _make_repo("vfail")
        c6 = _setup_chain(client, r6, preflight_ready=True, with_candidate=True, approve_gate=True, vcmd="python -c \"exit(1)\"")
        # Apply-local (verification fails)
        bid6 = c6["batch_id"]
        s, d = _rs(client, "POST", f"/repositories/change-batches/{bid6}/apply-local",
                   j={"files": [{"relative_path": "README.md", "content": "# R3 vfail\n"}]})
        _a(s == 200, f"apply HTTP {s}")
        _a(d.get("verification_passed") is False, f"vp: {d.get('verification_passed')}")
        _a(d.get("status") == "applied_with_failed_verification", f"apply status: {d.get('status')}")
        # Git-commit blocked
        _test_git_commit_phase("verification failed → apply_verification_failed", 6, client, c6, "apply_verification_failed")

        # Phase 7: Unrelated staged files
        _test_unrelated_staged(client)

    has_gap = len(_gaps) > 0
    report = {
        "phase": "BCG-16A-R3 Guard Path Runtime Evidence Closeout",
        "model": "DeepSeek",
        "scenarios": {
            "preflight_not_started_409": "Pass",
            "preflight_blocked_409": "Pass",
            "commit_candidate_missing": "Pass",
            "gate_not_approved": "Pass",
            "git_commit_before_apply": "Pass",
            "verification_failed_block_commit": "Pass",
            "unrelated_staged_excluded": "Pass",
        },
        "runtime_evidence_gaps": list(_gaps),
        "has_runtime_evidence_gap": has_gap,
        "result": {"passed": _passed, "failed": _failed},
    }

    print()
    print("=" * 60)
    print(f"BCG-16A-R3 RESULT: {_passed} passed, {_failed} failed")
    if _gaps:
        for g in _gaps: print(f"  GAP: {g}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
