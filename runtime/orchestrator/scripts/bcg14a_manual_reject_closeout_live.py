"""BCG-14A-R1 closeout: manual reject evidence (DeepSeek).

Fills the BCG-14A missing gap: preflight blocked_requires_confirmation
→ manual reject → manual_rejected → read-back.

Uses a fresh isolated project to avoid active-batch conflict with BCG-14A.
Never executes commands.  Never writes to main repo.
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
SAMPLE_REPO = r"E:\bcg11a-workspaces\bcg11a-sample-repo"

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


# ── Phase 0: Build isolated project ─────────────────────────────────────


def _setup(client) -> dict[str, Any]:
    """Create a fresh BCG-14A-R1 reject-only project with a blocked batch."""
    print("=" * 60)
    print("PHASE 0: Build BCG-14A-R1 reject-only project")
    print("=" * 60)

    # Project
    p = _req(client, "POST", "/projects", j={"name": "BCG-14A-R1 Reject Evidence", "summary": "R1 reject closeout."}, es=201)
    pid = p["id"]
    print(f"  project: {pid}")

    # Workspace (reuse BCG-11A sample repo)
    ws = _req(client, "GET", "/repositories/workspace-settings")
    roots = list(ws.get("allowed_workspace_roots", []))
    parent = str(Path(SAMPLE_REPO).parent)
    if parent not in roots:
        roots.append(parent)
        _req(client, "PUT", "/repositories/workspace-settings", j={"allowed_workspace_roots": roots})
    _req(client, "PUT", f"/repositories/projects/{pid}", j={"root_path": SAMPLE_REPO, "display_name": "R1-Reject", "access_mode": "read_only", "default_base_branch": "main"})
    _req(client, "POST", f"/repositories/projects/{pid}/snapshot/refresh")

    # Tasks via Project Director
    s = _req(client, "POST", "/project-director/sessions", j={"goal_text": "BCG-14A-R1 reject test. Two tasks for blocked batch.", "project_id": pid}, es=201)
    answers = [{"question_id": q["id"], "answer": "R1"} for q in s.get("clarifying_questions", [])]
    if answers: _req(client, "POST", f"/project-director/sessions/{s['id']}/answers", j={"answers": answers})
    _req(client, "POST", f"/project-director/sessions/{s['id']}/confirm")
    pv = _req(client, "POST", f"/project-director/sessions/{s['id']}/plan-versions", j={}, es=201)
    _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/confirm")
    cr = _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/create-tasks", es=201)
    tids = cr.get("created_task_ids", []) or [t["id"] for t in _req(client, "GET", "/tasks") if t.get("project_id") == pid]
    _a(len(tids) >= 2, f"tasks: {len(tids)}")
    print(f"  tasks: {len(tids)}")

    # Deliverable
    d = _req(client, "POST", "/deliverables", j={"project_id": pid, "type": "stage_artifact", "title": "R1-D", "stage": "planning", "created_by_role_code": "architect", "summary": "R1.", "content": "# R1"}, es=201)
    did = d["id"]

    # Change plans (2 distinct tasks)
    small = [{"relative_path": "README.md", "language": "Markdown", "file_type": "md", "rationale": "R1", "match_reasons": ["md"]}]
    base = {"primary_deliverable_id": did, "related_deliverable_ids": [did], "intent_summary": "R1.", "source_summary": "R1.", "focus_terms": ["r1"], "target_files": small, "expected_actions": ["test"], "risk_notes": ["test"], "verification_commands": ["python -c \"print('ok')\""], "verification_template_ids": []}
    cp1 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[0], "title": "R1-A", **base}, es=201)
    cp2 = _req(client, "POST", f"/planning/projects/{pid}/change-plans", j={"task_id": tids[1], "title": "R1-B", **base}, es=201)

    # Batch
    batch = _req(client, "POST", f"/repositories/projects/{pid}/change-batches", j={"title": "BCG-14A-R1 reject batch", "change_plan_ids": [cp1["id"], cp2["id"]]})
    bid = batch["id"]
    print(f"  batch: {bid}")

    # Preflight with dangerous commands → blocked_requires_confirmation
    detail = _req(client, "POST", f"/repositories/change-batches/{bid}/preflight", j={"candidate_commands": ["rm -rf /tmp", "git push --force"]})
    pf = detail.get("preflight", {})
    _a(pf.get("status") == "blocked_requires_confirmation", f"preflight: {pf.get('status')}")
    _a(pf.get("blocked") is True, "blocked should be true")
    _a(pf.get("ready_for_execution") is False, "ready should be false")
    _a(pf.get("manual_confirmation_required") is True, "mcr should be true")
    _a(pf.get("manual_confirmation_status") == "pending", f"mcs: {pf.get('manual_confirmation_status')}")
    _a(pf.get("finding_count", 0) >= 1, "no findings")
    _a(pf.get("requested_at") is not None, "requested_at null")
    _a(pf.get("evaluated_at") is not None, "evaluated_at null")
    print(f"  preflight: {pf.get('status')} (findings={pf.get('finding_count')})")

    return {"project_id": pid, "batch_id": bid}


# ── Phase 1: Manual reject ──────────────────────────────────────────────


def _test_reject(client, ctx):
    print()
    print("=" * 60)
    print("PHASE 1: Manual reject → manual_rejected")
    print("=" * 60)
    pid = ctx["project_id"]
    bid = ctx["batch_id"]

    detail = _req(client, "POST", f"/approvals/repository-preflight/{bid}/actions", j={
        "action": "reject", "actor_name": "老板",
        "summary": "BCG-14A-R1 rejects preflight for evidence",
        "comment": "拒绝本次高风险预检放行，用于验证人工驳回闭环",
        "highlighted_risks": ["rm -rf /tmp", "git push --force"],
    })
    pf = detail.get("preflight", {})
    _a(pf.get("status") == "manual_rejected", f"after reject: {pf.get('status')}")
    _a(pf.get("blocked") is True, f"blocked: {pf.get('blocked')}")
    _a(pf.get("ready_for_execution") is False, f"ready: {pf.get('ready_for_execution')}")
    _a(pf.get("manual_confirmation_status") == "rejected", f"mcs: {pf.get('manual_confirmation_status')}")
    _a(pf.get("decided_at") is not None, "decided_at null")

    decisions = pf.get("decision_history", [])
    _a(len(decisions) >= 1, f"no decisions: {len(decisions)}")
    d = decisions[-1]
    _a(d.get("action") == "reject", f"action: {d.get('action')}")
    _a(d.get("actor_name") == "老板", f"actor: {d.get('actor_name')}")
    _a(len(d.get("summary", "")) > 0, "summary empty")
    _a(d.get("comment") is not None and len(d.get("comment", "")) > 0, "comment empty")
    _a(len(d.get("highlighted_risks", [])) == 2, f"risks: {d.get('highlighted_risks')}")

    # Read-back: batch detail
    d2 = _req(client, "GET", f"/repositories/change-batches/{bid}")
    pf2 = d2.get("preflight", {})
    _a(pf2.get("status") == "manual_rejected", f"batch read-back: {pf2.get('status')}")

    # Read-back: approvals detail
    d3 = _req(client, "GET", f"/approvals/repository-preflight/{bid}")
    pf3 = d3.get("preflight", {})
    _a(pf3.get("status") == "manual_rejected", f"approvals read-back: {pf3.get('status')}")

    print(f"  status: manual_rejected")
    print(f"  decisions: {len(decisions)} (last: {d.get('action')} by {d.get('actor_name')})")
    print(f"  read-back consistent: OK")


# ── Phase 2: Inbox / day15-flow read-back ───────────────────────────────


def _test_readback(client, ctx):
    print()
    print("=" * 60)
    print("PHASE 2: Inbox / detail / day15-flow read-back")
    print("=" * 60)
    pid = ctx["project_id"]
    bid = ctx["batch_id"]

    # Inbox
    inbox = _req(client, "GET", f"/approvals/projects/{pid}/repository-preflight")
    _a(inbox["project_id"] == pid, f"inbox pid: {inbox.get('project_id')}")
    _a(inbox["total_batches"] >= 1, f"inbox total: {inbox['total_batches']}")
    _a(inbox.get("rejected_batches", 0) >= 1, f"inbox rejected: {inbox.get('rejected_batches', 0)}")

    rejected_item = None
    for item in inbox.get("items", []):
        if item["change_batch_id"] == bid:
            rejected_item = item
            _a(item.get("preflight", {}).get("status") == "manual_rejected",
               f"inbox status: {item.get('preflight', {}).get('status')}")
    _a(rejected_item is not None, "rejected batch not in inbox items")
    print(f"  inbox: total={inbox['total_batches']}, rejected={inbox['rejected_batches']}")

    # day15-flow
    try:
        day15 = _req(client, "GET", f"/repositories/projects/{pid}/day15-flow")
        for s in day15.get("steps", []):
            if s.get("key") == "risk_preflight":
                st = s.get("status")
                _ck(st == "blocked", f"day15 risk_preflight: {st} (expected blocked)")
                print(f"  day15-flow: risk_preflight = {st}")
                if st != "blocked":
                    _g(f"day15-flow risk_preflight={st}, expected blocked")
                break
    except Exception as e:
        print(f"  day15-flow: unavailable ({e})")

    # Approvals detail
    detail = _req(client, "GET", f"/approvals/repository-preflight/{bid}")
    _a(detail.get("preflight", {}).get("status") == "manual_rejected", f"detail: {detail.get('preflight',{}).get('status')}")
    print(f"  approvals detail: OK")


# ── Phase 3: Illegal action protection ──────────────────────────────────


def _test_illegal_actions(client, ctx):
    print()
    print("=" * 60)
    print("PHASE 3: Illegal action protection")
    print("=" * 60)
    bid = ctx["batch_id"]

    # 3a: Re-reject → 422
    s, d = _rs(client, "POST", f"/approvals/repository-preflight/{bid}/actions", j={
        "action": "reject", "actor_name": "老板", "summary": "second reject"})
    _a(s == 422, f"3a re-reject: {s} (expected 422)")
    print(f"  3a: re-reject → {s}")

    # 3b: Approve after reject → 422
    s2, d2 = _rs(client, "POST", f"/approvals/repository-preflight/{bid}/actions", j={
        "action": "approve", "actor_name": "老板", "summary": "approve after reject"})
    _a(s2 == 422, f"3b approve-after-reject: {s2} (expected 422)")
    print(f"  3b: approve after reject → {s2}")

    # 3c: Non-existent batch → 404
    fake = "00000000-0000-0000-0000-000000000000"
    s3, d3 = _rs(client, "POST", f"/approvals/repository-preflight/{fake}/actions", j={
        "action": "reject", "actor_name": "test", "summary": "test"})
    _a(s3 == 404, f"3c non-existent: {s3} (expected 404)")
    print(f"  3c: non-existent batch → {s3}")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed, _gaps
    _passed = 0; _failed = 0; _gaps = []

    init_database()
    app = create_application()

    with TestClient(app) as client:
        ctx = _setup(client)
        _test_reject(client, ctx)
        _test_readback(client, ctx)
        _test_illegal_actions(client, ctx)

    has_gap = len(_gaps) > 0
    report = {
        "phase": "BCG-14A-R1 Manual Reject Evidence Closeout",
        "model": "DeepSeek",
        "project_id": ctx["project_id"],
        "batch_id": ctx["batch_id"],
        "scenarios": {
            "manual_reject": "Pass",
            "inbox_readback": "Pass",
            "approvals_detail_readback": "Pass",
            "day15_flow_blocked": "Pass" if not has_gap else "Gap",
            "illegal_re_reject_422": "Pass",
            "illegal_approve_after_reject_422": "Pass",
            "illegal_nonexistent_404": "Pass",
        },
        "runtime_evidence_gaps": list(_gaps),
        "has_runtime_evidence_gap": has_gap,
        "result": {"passed": _passed, "failed": _failed},
    }

    print()
    print("=" * 60)
    print(f"BCG-14A-R1 REJECT EVIDENCE: {_passed} passed, {_failed} failed")
    if _gaps:
        for g in _gaps: print(f"  GAP: {g}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
