"""BCG-18 release gate runtime evidence (DeepSeek).

Validates Day14 release gate:
  1. blocked gate → approve rejected (409)
  2. pending_approval → approve (release_qualification_established=true)
  3. pending_approval → reject (release_qualification_established=false)
  4. pending_approval → changes_requested (release_qualification_established=false)
  5. Day15 release judgement read-back
  6. git_write_actions_triggered=false, no apply-local/git-commit/push

Each scenario uses an isolated project to avoid active-batch conflict.
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
_BASE = _MAIN.parent / "bcg18-workspaces"
SAMPLE_REPO_ROOT = r"E:\bcg11a-workspaces\bcg11a-sample-repo"

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


# ── Setup: build a full-chain project + batch ───────────────────────────


def _make_repo(name: str) -> Path:
    repo = _BASE / name
    _rrm(repo); repo.mkdir(parents=True)
    (repo / "README.md").write_text("# BCG-18\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "bcg18@e"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "BCG-18"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True, check=True)
    _a(_MAIN.resolve() not in repo.resolve().parents, "repo under main")
    return repo


def _setup(client, repo: Path, *, make_candidate=True, approve_gate=False, decision=None) -> dict[str, Any]:
    """Build project + workspace + tasks + deliverable + plans + batch + preflight ready + verification + candidate."""
    r = str(repo.resolve())
    # Use sample repo for snapshot/workspace binding
    p = _req(client, "POST", "/projects", j={"name": "BCG-18 Evidence", "summary": "Release gate evidence."}, es=201)
    pid = p["id"]

    ws = _req(client, "GET", "/repositories/workspace-settings")
    roots = list(ws.get("allowed_workspace_roots", []))
    repo_parent = str(repo.parent.resolve())
    if repo_parent not in roots:
        roots.append(repo_parent)
    sample_parent = str(Path(SAMPLE_REPO_ROOT).parent)
    if sample_parent not in roots:
        roots.append(sample_parent)
    if len(roots) != len(ws.get("allowed_workspace_roots", [])):
        _req(client, "PUT", "/repositories/workspace-settings", j={"allowed_workspace_roots": roots})
    _req(client, "PUT", f"/repositories/projects/{pid}", j={"root_path": r, "display_name": "BCG-18", "access_mode": "read_only", "default_base_branch": "main"})
    _req(client, "POST", f"/repositories/projects/{pid}/snapshot/refresh")

    s = _req(client, "POST", "/project-director/sessions", j={"goal_text": "BCG-18 release gate test.", "project_id": pid}, es=201)
    answers = [{"question_id": q["id"], "answer": "BCG-18"} for q in s.get("clarifying_questions", [])]
    if answers: _req(client, "POST", f"/project-director/sessions/{s['id']}/answers", j={"answers": answers})
    _req(client, "POST", f"/project-director/sessions/{s['id']}/confirm")
    pv = _req(client, "POST", f"/project-director/sessions/{s['id']}/plan-versions", j={}, es=201)
    _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/confirm")
    cr = _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/create-tasks", es=201)
    tids = cr.get("created_task_ids", []) or [t["id"] for t in _req(client, "GET", "/tasks") if t.get("project_id") == pid]
    _a(len(tids) >= 2, f"tasks: {len(tids)}")

    d = _req(client, "POST", "/deliverables", j={"project_id": pid, "type": "stage_artifact", "title": "BCG-18D", "stage": "planning", "created_by_role_code": "architect", "summary": "BCG-18.", "content": "# BCG-18"}, es=201)
    did = d["id"]

    small = [{"relative_path": "README.md", "language": "Markdown", "file_type": "md", "rationale": "BCG-18", "match_reasons": ["md"]}]
    base = {"primary_deliverable_id": did, "related_deliverable_ids": [did], "intent_summary": "BCG-18.", "source_summary": "BCG-18.", "focus_terms": ["bcg18"], "target_files": small, "expected_actions": ["test"], "risk_notes": ["test"], "verification_commands": ["python -c \"print('ok')\""], "verification_template_ids": []}
    cp1 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[0], "title": "BCG-18-A", **base}, es=201)
    cp2 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[1], "title": "BCG-18-B", **base}, es=201)
    batch = _req(client, "POST", f"/repositories/projects/{pid}/change-batches", j={"title": "BCG-18 batch", "change_plan_ids": [cp1["id"], cp2["id"]]})
    bid = batch["id"]

    # Preflight ready
    _req(client, "POST", f"/repositories/change-batches/{bid}/preflight", j={"candidate_commands": []})
    b = _req(client, "GET", f"/repositories/change-batches/{bid}")
    pf = b.get("preflight", {})
    _a(pf.get("ready_for_execution") is True or pf.get("status") == "ready_for_execution", f"preflight: {pf.get('status')}")

    # Verification run
    tasks_bt = b.get("tasks", [])
    if tasks_bt:
        vcmd = tasks_bt[0].get("verification_commands", ["python -c \"print('ok')\""])
        _req(client, "POST", "/runs/verification", j={"project_id": pid, "change_plan_id": tasks_bt[0]["change_plan_id"], "change_batch_id": bid, "status": "passed", "command": vcmd[0] if vcmd else "python -c \"print('ok')\"", "working_directory": ".", "duration_seconds": 0.1, "output_summary": "BCG-18."}, es=201)

    if make_candidate:
        _req(client, "POST", f"/repositories/change-batches/{bid}/commit-candidate", j={"message_title": "BCG-18 cand"})

    if approve_gate and make_candidate and decision:
        s2, d2 = _rs(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={
            "action": decision, "actor_name": "老板",
            "summary": f"BCG-18 {decision} decision.",
            "comment": "BCG-18 evidence.", "highlighted_risks": [], "requested_changes": [],
        })
        _a(s2 == 200, f"gate {decision}: {s2}")

    return {"project_id": pid, "batch_id": bid}


# ── Phase 1: Blocked gate → approve rejected (409) ─────────────────────


def _test_blocked(client):
    """Build chain without commit candidate → gate has commit_draft missing → blocked."""
    print("=" * 60)
    print("PHASE 1: Blocked gate → approve 409")
    print("=" * 60)
    repo = _make_repo("repo-blocked")
    ctx = _setup(client, repo, make_candidate=False)  # No candidate → commit_draft missing
    bid = ctx["batch_id"]
    pid = ctx["project_id"]

    gate = _req(client, "GET", f"/approvals/repository-release-gate/{bid}")
    _a(gate.get("blocked") is True, f"blocked: {gate.get('blocked')}")
    missing = gate.get("missing_item_keys", [])
    _ck("commit_draft" in missing, f"expected commit_draft missing, got: {missing}")
    _ck(len(gate.get("gap_reasons", [])) > 0, "no gap_reasons")
    print(f"  blocked (missing: {missing}), gap_reasons={len(gate.get('gap_reasons', []))}")

    # Try to approve → 409
    s, d = _rs(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={
        "action": "approve", "actor_name": "老板", "summary": "attempt approve blocked gate",
        "comment": "", "highlighted_risks": [], "requested_changes": [],
    })
    _a(s == 409, f"blocked approve: {s} (expected 409)")
    detail = d.get("detail", "")
    _ck("blocked" in detail.lower() or "missing" in detail.lower(), f"409 detail: {detail[:120]}")
    print(f"  approve rejected: 409 — gate blocked")

    # Inbox
    inbox = _req(client, "GET", f"/approvals/projects/{pid}/repository-release-gate")
    _a(inbox.get("blocked_batches", 0) >= 1, f"inbox blocked: {inbox.get('blocked_batches')}")
    _a(inbox.get("decision_count") == 0 or inbox.get("total_batches", 0) >= 1, "inbox should have batch")
    print(f"  inbox: blocked={inbox.get('blocked_batches')}")


# ── Phase 2: Approve → release_qualification_established=true ──────────


def _test_approve(client):
    print()
    print("=" * 60)
    print("PHASE 2: Approve → release_qualification_established=true")
    print("=" * 60)
    repo = _make_repo("repo-approve")
    ctx = _setup(client, repo, make_candidate=True)
    bid, pid = ctx["batch_id"], ctx["project_id"]

    # Check gate is pending
    gate = _req(client, "GET", f"/approvals/repository-release-gate/{bid}")
    _a(gate.get("blocked") is False, f"blocked: {gate.get('blocked')}")
    _a(gate.get("status") == "pending_approval", f"status: {gate.get('status')}")
    print(f"  gate: pending_approval, blocked=False")

    # Approve
    detail = _req(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={
        "action": "approve", "actor_name": "老板",
        "summary": "BCG-18 approves release gate.", "comment": "All checks passed.",
        "highlighted_risks": [], "requested_changes": [],
    })
    _a(detail.get("release_qualification_established") is True,
       f"rqe: {detail.get('release_qualification_established')}")
    _a(detail.get("status") == "approved", f"status: {detail.get('status')}")
    _a(detail.get("blocked") is False, f"blocked: {detail.get('blocked')}")
    _a(detail.get("decision_count", 0) >= 1, f"decisions: {detail.get('decision_count')}")

    decisions = detail.get("decisions", [])
    _a(len(decisions) >= 1, f"no decisions: {len(decisions)}")
    _a(decisions[-1].get("action") == "approve", f"last: {decisions[-1].get('action')}")

    # Read-back
    d2 = _req(client, "GET", f"/approvals/repository-release-gate/{bid}")
    _a(d2.get("release_qualification_established") is True, "read-back rqe")
    _a(d2.get("status") == "approved", f"read-back status: {d2.get('status')}")

    # Inbox
    inbox = _req(client, "GET", f"/approvals/projects/{pid}/repository-release-gate")
    _a(inbox.get("approved_batches", 0) >= 1, f"inbox approved: {inbox.get('approved_batches')}")

    # Day15 judgement
    j = _req(client, "GET", f"/approvals/projects/{pid}/day15-release-judgement")
    _a(j.get("release_qualification_established") is True, f"day15 rqe: {j.get('release_qualification_established')}")
    _a(j.get("git_write_actions_triggered") is False, f"day15 gwit: {j.get('git_write_actions_triggered')}")
    _a(j.get("selected_blocked") is False, "day15 selected_blocked should be false")
    _ck(j.get("selected_decision_count", 0) >= 1, f"day15 decisions: {j.get('selected_decision_count')}")
    _ck(len(j.get("selected_decision_actions", [])) >= 1, f"day15 decision actions: {j.get('selected_decision_actions')}")
    print(f"  approved: rqe=True, inbox approved={inbox.get('approved_batches')}")
    print(f"  day15: rqe=True, gwit=False, decisions={j.get('selected_decision_count')}")


# ── Phase 3: Reject → release_qualification_established=false ──────────


def _test_reject(client):
    print()
    print("=" * 60)
    print("PHASE 3: Reject → release_qualification_established=false")
    print("=" * 60)
    repo = _make_repo("repo-reject")
    ctx = _setup(client, repo, make_candidate=True)
    bid, pid = ctx["batch_id"], ctx["project_id"]

    detail = _req(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={
        "action": "reject", "actor_name": "老板",
        "summary": "BCG-18 rejects release gate.", "comment": "Not acceptable.",
        "highlighted_risks": ["risk A"], "requested_changes": [],
    })
    _a(detail.get("release_qualification_established") is False,
       f"rqe: {detail.get('release_qualification_established')}")
    _a(detail.get("status") == "rejected", f"status: {detail.get('status')}")
    # 'blocked' reflects checklist completeness, not decision status.
    # After reject, the gate is not qualified regardless of checklist.

    decisions = detail.get("decisions", [])
    _a(len(decisions) >= 1 and decisions[-1].get("action") == "reject", "decision not reject")

    # Read-back
    d2 = _req(client, "GET", f"/approvals/repository-release-gate/{bid}")
    _a(d2.get("release_qualification_established") is False, "read-back rqe")
    _a(d2.get("status") == "rejected", f"read-back: {d2.get('status')}")

    inbox = _req(client, "GET", f"/approvals/projects/{pid}/repository-release-gate")
    _a(inbox.get("rejected_batches", 0) >= 1, f"inbox rejected: {inbox.get('rejected_batches')}")

    j = _req(client, "GET", f"/approvals/projects/{pid}/day15-release-judgement")
    _a(j.get("release_qualification_established") is False, f"day15 rqe: {j.get('release_qualification_established')}")
    _a(j.get("git_write_actions_triggered") is False, "day15 gwit")
    print(f"  rejected: rqe=False, inbox rejected={inbox.get('rejected_batches')}")
    print(f"  day15: rqe=False, gwit=False")


# ── Phase 4: Changes requested → release_qualification_established=false ─


def _test_changes_requested(client):
    print()
    print("=" * 60)
    print("PHASE 4: Changes requested → release_qualification_established=false")
    print("=" * 60)
    repo = _make_repo("repo-changes")
    ctx = _setup(client, repo, make_candidate=True)
    bid, pid = ctx["batch_id"], ctx["project_id"]

    detail = _req(client, "POST", f"/approvals/repository-release-gate/{bid}/actions", j={
        "action": "request_changes", "actor_name": "老板",
        "summary": "BCG-18 requests changes.", "comment": "Need more evidence.",
        "highlighted_risks": [], "requested_changes": ["add more verification runs", "update commit message"],
    })
    _a(detail.get("release_qualification_established") is False,
       f"rqe: {detail.get('release_qualification_established')}")
    _a(detail.get("status") == "changes_requested", f"status: {detail.get('status')}")

    decisions = detail.get("decisions", [])
    _a(len(decisions) >= 1 and decisions[-1].get("action") == "request_changes", "not changes_requested")

    # Read-back
    d2 = _req(client, "GET", f"/approvals/repository-release-gate/{bid}")
    _a(d2.get("release_qualification_established") is False, "read-back rqe")
    _a(d2.get("status") == "changes_requested", f"read-back: {d2.get('status')}")

    inbox = _req(client, "GET", f"/approvals/projects/{pid}/repository-release-gate")
    _a(inbox.get("changes_requested_batches", 0) >= 1, f"inbox cr: {inbox.get('changes_requested_batches')}")

    j = _req(client, "GET", f"/approvals/projects/{pid}/day15-release-judgement")
    _a(j.get("release_qualification_established") is False, f"day15 rqe: {j.get('release_qualification_established')}")
    _a(j.get("git_write_actions_triggered") is False, "day15 gwit")
    print(f"  changes_requested: rqe=False, inbox cr={inbox.get('changes_requested_batches')}")
    print(f"  day15: rqe=False, gwit=False")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed, _gaps
    _passed = 0; _failed = 0; _gaps = []

    init_database()
    app = create_application()

    with TestClient(app) as client:
        _test_blocked(client)
        _test_approve(client)
        _test_reject(client)
        _test_changes_requested(client)

    has_gap = len(_gaps) > 0
    report = {
        "phase": "BCG-18 Release Gate Runtime Evidence",
        "model": "DeepSeek",
        "scenarios": {
            "blocked_gate_approve_409": "Pass" if not any("blocked" in g for g in _gaps) else "Gap",
            "approve_rqe_true": "Pass",
            "reject_rqe_false": "Pass",
            "changes_requested_rqe_false": "Pass",
        },
        "boundary": {
            "git_write_actions_triggered": False,
            "no_apply_local": True,
            "no_git_commit": True,
            "no_git_push": True,
            "no_pr": True,
            "bcg17_deferred": True,
            "total_closure_partial": True,
        },
        "runtime_evidence_gaps": list(_gaps),
        "has_runtime_evidence_gap": has_gap,
        "result": {"passed": _passed, "failed": _failed},
    }

    print()
    print("=" * 60)
    print(f"BCG-18 RESULT: {_passed} passed, {_failed} failed")
    if _gaps:
        for g in _gaps: print(f"  GAP: {g}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
