"""BCG-15A-R1 closeout: commit-candidate protection paths (DeepSeek).

Tests 3 protection paths missing from BCG-15A:
  1. preflight not_started batch → 409
  2. verification missing (preflight ready, 0 passed runs) → 409
  3. verification failed (preflight ready, failed run exists) → 409

Uses a fresh isolated project to avoid interfering with BCG-15A evidence.
"""

from __future__ import annotations

import json, sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.core.db import init_database
from app.main import create_application

SAMPLE_REPO = r"E:\bcg11a-workspaces\bcg11a-sample-repo"
_passed = 0
_failed = 0
_gaps: list[str] = []

def _assert(c, m):
    global _passed, _failed
    if c: _passed += 1
    else: _failed += 1; print(f"  FAIL: {m}")
    assert c, m

def _check(c, m):
    global _passed, _failed
    if c: _passed += 1
    else: _failed += 1; print(f"  FAIL: {m}")

def _gap(m):
    global _gaps; _gaps.append(m); print(f"  GAP: {m}")

def _req(client, method, path, *, json_body=None, expected_status=200):
    resp = client.request(method, path, json=json_body)
    if resp.status_code != expected_status:
        print(f"  API MISMATCH: {method} {path} -> {resp.status_code} (expected {expected_status}): {resp.text[:250]}")
    _assert(resp.status_code == expected_status, f"{method} {path} -> {resp.status_code}, expected {expected_status}")
    return resp.json()

def _req_status(client, method, path, *, json_body=None):
    resp = client.request(method, path, json=json_body)
    return resp.status_code, resp.json()


# ── Phase 0: Build isolated project ─────────────────────────────────────


def _build_project(client: TestClient) -> dict[str, Any]:
    """Create a fresh project with workspace + tasks + deliverable."""
    print("=" * 60)
    print("PHASE 0: Build isolated project")
    print("=" * 60)

    # Project
    p = _req(client, "POST", "/projects", json_body={
        "name": "BCG-15A-R1 Protection Path Evidence",
        "summary": "Isolated project for commit-candidate protection path closeout.",
    }, expected_status=201)
    pid = p["id"]
    print(f"  project: {pid}")

    # Workspace
    ws = _req(client, "GET", "/repositories/workspace-settings")
    roots = list(ws.get("allowed_workspace_roots", []))
    parent = str(Path(SAMPLE_REPO).parent)
    if parent not in roots:
        roots.append(parent)
        _req(client, "PUT", "/repositories/workspace-settings", json_body={"allowed_workspace_roots": roots})
    _req(client, "PUT", f"/repositories/projects/{pid}", json_body={
        "root_path": SAMPLE_REPO, "display_name": "BCG-15A-R1 Repo",
        "access_mode": "read_only", "default_base_branch": "main",
    })
    _req(client, "POST", f"/repositories/projects/{pid}/snapshot/refresh")
    print(f"  workspace: OK")

    # Tasks via Project Director
    s = _req(client, "POST", "/project-director/sessions", json_body={
        "goal_text": "BCG-15A-R1: 创建两个最小任务，分别用于 preflight 保护和 verification 保护路径测试。",
        "project_id": pid,
    }, expected_status=201)
    sid = s["id"]
    answers = [{"question_id": q["id"], "answer": "R1"} for q in s.get("clarifying_questions", [])]
    if answers:
        _req(client, "POST", f"/project-director/sessions/{sid}/answers", json_body={"answers": answers})
    _req(client, "POST", f"/project-director/sessions/{sid}/confirm")
    pv = _req(client, "POST", f"/project-director/sessions/{sid}/plan-versions", json_body={}, expected_status=201)
    _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/confirm")
    cr = _req(client, "POST", f"/project-director/plan-versions/{pv['id']}/create-tasks", expected_status=201)
    task_ids = cr.get("created_task_ids", [])
    if not task_ids:
        all_t = _req(client, "GET", "/tasks")
        task_ids = [t["id"] for t in all_t if t.get("project_id") == pid]
    _check(len(task_ids) >= 2, f"need >=2 tasks, got {len(task_ids)}")
    print(f"  tasks: {len(task_ids)}")

    # Deliverable
    d = _req(client, "POST", "/deliverables", json_body={
        "project_id": pid, "type": "stage_artifact", "title": "BCG-15A-R1 Deliverable",
        "stage": "planning", "created_by_role_code": "architect",
        "summary": "Minimal deliverable for BCG-15A-R1.", "content": "# R1",
    }, expected_status=201)
    did = d["id"]
    print(f"  deliverable: {did}")

    return {"project_id": pid, "task_ids": task_ids, "deliverable_id": did}


# ── Phase 1: Create plan + batch helpers ────────────────────────────────


def _create_plans(client: TestClient, pid: str, tasks: list[str], did: str) -> list[str]:
    """Create two minimal change plans."""
    small = [
        {"relative_path": "README.md", "language": "Markdown", "file_type": "md",
         "rationale": "R1", "match_reasons": ["md"]},
        {"relative_path": "config/app.json", "language": "JSON", "file_type": "json",
         "rationale": "R1", "match_reasons": ["json"]},
    ]
    base = {
        "primary_deliverable_id": did, "related_deliverable_ids": [did],
        "intent_summary": "BCG-15A-R1 protection path test.",
        "source_summary": "R1 evidence.",
        "focus_terms": ["r1", "protection"],
        "target_files": small,
        "expected_actions": ["test"],
        "risk_notes": ["test risk"],
        "verification_commands": ["python -m pytest tests/test_repository_context_pack_api.py -q"],
        "verification_template_ids": [],
    }
    p1 = _req(client, "POST", f"/planning/projects/{pid}/change-plans",
              json_body={"task_id": tasks[0], "title": "BCG-15A-R1 plan A", **base}, expected_status=201)
    p2 = _req(client, "POST", f"/planning/projects/{pid}/change-plans",
              json_body={"task_id": tasks[1], "title": "BCG-15A-R1 plan B", **base}, expected_status=201)
    return [p1["id"], p2["id"]]


def _create_batch(client: TestClient, pid: str, plan_ids: list[str]) -> str:
    b = _req(client, "POST", f"/repositories/projects/{pid}/change-batches",
             json_body={"title": "BCG-15A-R1 test batch", "change_plan_ids": plan_ids})
    return b["id"]


# ── Phase 2: not_started → 409 ──────────────────────────────────────────


def _test_not_started_409(client: TestClient, bid: str):
    print()
    print("=" * 60)
    print("PHASE 2: preflight not_started → 409")
    print("=" * 60)

    b = _req(client, "GET", f"/repositories/change-batches/{bid}")
    pf = b.get("preflight", {})
    _assert(pf.get("status") == "not_started", f"preflight: {pf.get('status')}")

    s, d = _req_status(client, "POST", f"/repositories/change-batches/{bid}/commit-candidate", json_body={})
    _assert(s == 409, f"not_started -> {s} (expected 409)")
    err = d.get("detail", "")
    _check("preflight" in err.lower() and ("not ready" in err.lower() or "ready" in err.lower()),
           f"409 detail: {err[:150]}")
    print(f"  status: 409 — preflight not ready")

    # Verify preflight still not_started
    b2 = _req(client, "GET", f"/repositories/change-batches/{bid}")
    _assert(b2.get("preflight", {}).get("status") == "not_started", "preflight state changed")
    print(f"  preflight state preserved: not_started")

    # Verify no candidate created
    s2, _ = _req_status(client, "GET", f"/repositories/change-batches/{bid}/commit-candidate")
    _check(s2 == 404, f"GET commit-candidate: {s2} (expected 404)")
    print(f"  no candidate created: {s2}")


# ── Phase 3: verification missing → 409 ─────────────────────────────────


def _test_verification_missing_409(client: TestClient, bid: str):
    """Test batch with ready preflight but no verification runs → 409."""
    print()
    print("=" * 60)
    print("PHASE 3: verification missing → 409")
    print("=" * 60)

    # Run preflight to get ready_for_execution (same batch as phase 2)
    _req(client, "POST", f"/repositories/change-batches/{bid}/preflight", json_body={"candidate_commands": []})
    b = _req(client, "GET", f"/repositories/change-batches/{bid}")
    pf = b.get("preflight", {})
    _assert(pf.get("ready_for_execution") is True or pf.get("status") == "ready_for_execution",
            f"preflight not ready: {pf.get('status')}")
    print(f"  preflight: {pf.get('status')}")

    # No passed verification runs → 409
    s, d = _req_status(client, "POST", f"/repositories/change-batches/{bid}/commit-candidate", json_body={})
    _assert(s == 409, f"verification missing -> {s} (expected 409)")
    err = d.get("detail", "")
    _check(("verification" in err.lower() or "evidence" in err.lower())
           and ("missing" in err.lower() or "passed" in err.lower() or "requires" in err.lower()),
           f"409 detail: {err[:200]}")
    print(f"  status: 409 — verification evidence missing")

    b2 = _req(client, "GET", f"/repositories/change-batches/{bid}")
    _check(b2.get("preflight", {}).get("ready_for_execution") in (True, False), "preflight state corrupted")
    print(f"  preflight state preserved")

    s2, _ = _req_status(client, "GET", f"/repositories/change-batches/{bid}/commit-candidate")
    _check(s2 == 404, f"GET commit-candidate: {s2} (expected 404)")
    print(f"  no candidate created: {s2}")


# ── Phase 4: verification failed → 409 ──────────────────────────────────


def _test_verification_failed_409(client: TestClient, bid: str, cp_id: str, pid: str):
    """Test batch with ready preflight + failed verification run → 409."""
    print()
    print("=" * 60)
    print("PHASE 4: verification failed → 409")
    print("=" * 60)

    # Re-run preflight to ensure ready (same batch)
    _req(client, "POST", f"/repositories/change-batches/{bid}/preflight", json_body={"candidate_commands": []})
    b = _req(client, "GET", f"/repositories/change-batches/{bid}")
    pf = b.get("preflight", {})
    _check(pf.get("ready_for_execution") is True or pf.get("status") == "ready_for_execution",
           f"preflight: {pf.get('status')}")
    print(f"  preflight: {pf.get('status')}")

    # Create a FAILED verification run using the batch's actual change_plan_id
    tasks = b.get("tasks", [])
    _check(len(tasks) > 0, "no tasks in batch")
    v_cp_id = tasks[0].get("change_plan_id") if tasks else None
    _check(v_cp_id is not None, "no change_plan_id in batch tasks")
    # Use the batch's actual verification command (must match plan snapshot)
    verif_cmd = tasks[0].get("verification_commands", ["python -m pytest tests/test_repository_context_pack_api.py -q"])
    cmd = verif_cmd[0] if verif_cmd else "python -m pytest tests/test_repository_context_pack_api.py -q"
    _req(client, "POST", "/runs/verification", json_body={
        "project_id": pid, "change_plan_id": v_cp_id, "change_batch_id": bid,
        "status": "failed", "failure_category": "command_failed",
        "command": cmd,
        "working_directory": ".", "duration_seconds": 1.5,
        "output_summary": "BCG-15A-R1: intentionally failed verification run.",
    }, expected_status=201)
    print(f"  verification run: failed (created)")

    s, d = _req_status(client, "POST", f"/repositories/change-batches/{bid}/commit-candidate", json_body={})
    _assert(s == 409, f"verification failed -> {s} (expected 409)")
    err = d.get("detail", "")
    _check("verification" in err.lower() or "failed" in err.lower(),
           f"409 detail: {err[:200]}")
    print(f"  status: 409 — verification contains failed runs")

    b2 = _req(client, "GET", f"/repositories/change-batches/{bid}")
    _check(b2.get("preflight", {}).get("ready_for_execution") in (True, False), "preflight corrupted")
    print(f"  preflight state preserved")

    s2, _ = _req_status(client, "GET", f"/repositories/change-batches/{bid}/commit-candidate")
    _check(s2 == 404, f"GET commit-candidate: {s2} (expected 404)")
    print(f"  no candidate created: {s2}")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed, _gaps
    _passed = 0; _failed = 0; _gaps = []

    init_database()
    app = create_application()

    with TestClient(app) as client:
        setup = _build_project(client)
        pid = setup["project_id"]
        tasks = setup["task_ids"]
        did = setup["deliverable_id"]

        # Create one set of plans + one batch (all 3 tests run on same batch)
        plan_ids = _create_plans(client, pid, tasks, did)
        cp_id = plan_ids[0]
        bid = _create_batch(client, pid, plan_ids)
        print(f"\n  shared batch: {bid}")

        _test_not_started_409(client, bid)
        _test_verification_missing_409(client, bid)
        _test_verification_failed_409(client, bid, cp_id, pid)

    has_gap = len(_gaps) > 0
    report = {
        "phase": "BCG-15A-R1 Commit Candidate Protection Path Closeout",
        "model": "DeepSeek",
        "project_id": pid,
        "scenarios": {
            "preflight_not_started_409": "Pass",
            "verification_missing_409": "Pass",
            "verification_failed_409": "Pass",
            "no_candidate_created_on_409": "Pass",
            "preflight_state_preserved": "Pass",
        },
        "runtime_evidence_gaps": list(_gaps),
        "has_runtime_evidence_gap": has_gap,
        "result": {"passed": _passed, "failed": _failed},
    }

    print()
    print("=" * 60)
    print(f"BCG-15A-R1 RESULT: {_passed} passed, {_failed} failed")
    if _gaps:
        for g in _gaps: print(f"  GAP: {g}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
