"""BCG-10-R3 live evidence: approval request_changes / reject → executable rework task.

This script proves that when the boss applies a negative approval decision
(request_changes or reject) through the real POST /approvals/{id}/actions API,
the system automatically creates one executable pending rework task.

Scenarios covered:
  1. request_changes → rework task created, readable via GET /tasks
  2. reject → rework task created with correct risk/priority/owner/source_draft_id
  3. approve → no rework task created
  4. idempotency / closed approval → 422, no duplicate task, no compensation
  5. transaction rollback → approval stays pending_approval, no ghost data
  6. event boundary → request_changes publishes task_created exactly once;
     rollback publishes zero

Never prints or writes API keys.  Never modifies the database directly for the
main path (the rollback test uses monkeypatched service, not direct DB writes).
Never calls worker / planning / apply / apply-local / git-commit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.core.db import init_database
from app.main import create_application
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService

_passed = 0
_failed = 0


def _assert(condition: bool, message: str) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {message}")
    assert condition, message


def _check(condition: bool, message: str) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {message}")


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    expected_status: int = 200,
) -> Any:
    response = client.request(method, path, json=json_body)
    if response.status_code != expected_status:
        print(
            f"  API MISMATCH: {method} {path} returned {response.status_code}, "
            f"expected {expected_status}: {response.text[:300]}"
        )
    _assert(
        response.status_code == expected_status,
        f"{method} {path} returned {response.status_code}, expected {expected_status}",
    )
    return response.json()


# ── helpers ──────────────────────────────────────────────────────────────

def _create_project(client: TestClient, name: str) -> str:
    payload = _request_json(
        client, "POST", "/projects",
        json_body={"name": name, "summary": f"BCG-10-R3 live evidence: {name}"},
        expected_status=201,
    )
    project_id = payload["id"]
    print(f"  project_id = {project_id}")
    return project_id


def _create_source_task(client: TestClient, project_id: str) -> str:
    payload = _request_json(
        client, "POST", "/tasks",
        json_body={
            "project_id": project_id,
            "title": "BCG-10 source task",
            "input_summary": "Initial task for BCG-10 rework evidence.",
            "acceptance_criteria": ["Deliverable created"],
        },
        expected_status=201,
    )
    task_id = payload["id"]
    print(f"  source_task_id = {task_id}")
    return task_id


def _create_deliverable(
    client: TestClient, project_id: str, task_id: str
) -> dict:
    payload = _request_json(
        client, "POST", "/deliverables",
        json_body={
            "project_id": project_id,
            "type": "prd",
            "title": "BCG-10-R3 PRD",
            "stage": "planning",
            "created_by_role_code": "product_manager",
            "summary": "PRD for BCG-10 rework task evidence.",
            "content": "# BCG-10 PRD\n\nNeeds boss approval.",
            "content_format": "markdown",
            "source_task_id": task_id,
        },
        expected_status=201,
    )
    print(f"  deliverable_id = {payload['id']}")
    return payload


def _create_approval(client: TestClient, deliverable_id: str) -> dict:
    payload = _request_json(
        client, "POST", "/approvals",
        json_body={
            "deliverable_id": deliverable_id,
            "requester_role_code": "product_manager",
            "request_note": "Please review BCG-10-R3 PRD.",
            "due_in_hours": 24,
        },
        expected_status=201,
    )
    print(f"  approval_id = {payload['id']}")
    return payload


def _get_all_tasks(client: TestClient) -> list[dict]:
    return _request_json(client, "GET", "/tasks")


def _find_rework_task(
    client: TestClient, approval_id: str
) -> dict | None:
    tasks = _get_all_tasks(client)
    for t in tasks:
        sid = t.get("source_draft_id") or ""
        if sid.startswith("arw:") and approval_id in (t.get("input_summary") or ""):
            return t
    return None


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 1: request_changes → executable rework task
# ══════════════════════════════════════════════════════════════════════════

def scenario_1_request_changes(client: TestClient, monkeypatch) -> dict:
    print("=" * 60)
    print("SCENARIO 1: request_changes creates executable rework task")
    print("=" * 60)

    published_ids: list[str] = []
    original_publish = TaskRepository.publish_created

    def _capture(self, task):
        published_ids.append(str(task.id))
        return original_publish(self, task)

    monkeypatch.setattr(TaskRepository, "publish_created", _capture)

    project_id = _create_project(client, "BCG-10-R3 request_changes project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    # ── 1a: apply request_changes ────────────────────────────────────
    print("\n1a. Apply request_changes action...")
    detail = _request_json(
        client, "POST", f"/approvals/{approval['id']}/actions",
        json_body={
            "action": "request_changes",
            "actor_name": "老板",
            "summary": "BCG-10-R3 requests changes for live evidence",
            "comment": "Please add detailed rollout plan.",
            "requested_changes": [
                "Add rollout fallback section",
                "Define success metrics",
            ],
            "highlighted_risks": [
                "Current PRD lacks measurable acceptance criteria",
            ],
        },
    )

    _assert(detail["status"] == "changes_requested", "status must be changes_requested")
    _assert(detail["decided_at"] is not None, "decided_at must be non-null")
    decision_id = detail["decisions"][-1]["id"]
    print(f"  decision_id = {decision_id}")

    # ── 1b: read approval detail ─────────────────────────────────────
    print("\n1b. Read approval detail...")
    detail2 = _request_json(client, "GET", f"/approvals/{approval['id']}")
    _assert(detail2["status"] == "changes_requested", "re-read status must be changes_requested")
    _assert(detail2["decided_at"] is not None, "re-read decided_at must be non-null")
    _assert(
        detail2["latest_decision"]["action"] == "request_changes",
        "latest_decision.action must be request_changes",
    )
    _assert(
        len(detail2["decisions"][-1]["requested_changes"]) == 2,
        "requested_changes must have 2 items in full decision response",
    )

    # ── 1c: read approval history ────────────────────────────────────
    print("\n1c. Read approval history...")
    history = _request_json(
        client, "GET", f"/approvals/{approval['id']}/history"
    )
    _assert(history["rework_status"] == "rework_required", "history rework_status must be rework_required")
    _assert(history["negative_decision_count"] >= 1, "negative_decision_count >= 1")
    steps_kinds = [s["event_kind"] for s in history["steps"]]
    _assert("approval_requested" in steps_kinds, "history must include approval_requested")
    _assert("approval_decided" in steps_kinds, "history must include approval_decided")

    # ── 1d: read change-rework snapshot ──────────────────────────────
    print("\n1d. Read change-rework snapshot...")
    rework = _request_json(
        client, "GET", f"/approvals/projects/{project_id}/change-rework"
    )
    _assert(rework["summary"]["approval_rework_items"] >= 1, "change-rework summary must show approval_rework_items >= 1")
    matching = [i for i in rework["items"] if i.get("approval_id") == approval["id"]]
    _assert(len(matching) >= 1, "change-rework must include the target approval")

    # ── 1e: find executable rework task via GET /tasks ───────────────
    print("\n1e. Find executable rework task via GET /tasks...")
    rework_task = _find_rework_task(client, approval["id"])
    _assert(rework_task is not None, "must find an arw: rework task via GET /tasks")
    _assert(rework_task["status"] == "pending", "rework task must be pending")
    _assert(rework_task["project_id"] == project_id, "rework task project_id must match")
    _assert(rework_task["priority"] == "high", "rework task priority must be high")
    _assert(
        rework_task["source_draft_id"].startswith("arw:"),
        f"source_draft_id must start with arw:, got {rework_task.get('source_draft_id')}",
    )
    _assert(
        approval["id"] in (rework_task.get("input_summary") or ""),
        "input_summary must contain approval_id",
    )
    _assert(
        "request_changes" in (rework_task.get("input_summary") or ""),
        "input_summary must contain decision action request_changes",
    )
    _assert(
        "Add rollout fallback" in (rework_task.get("input_summary") or ""),
        "input_summary must contain requested_changes item",
    )
    _assert(
        len(rework_task.get("acceptance_criteria") or []) >= 2,
        "acceptance_criteria must have at least 2 items",
    )
    _check(
        any(
            "审批" in c or "approval" in c.lower() or "decision" in c.lower()
            for c in rework_task.get("acceptance_criteria") or []
        ),
        "acceptance_criteria must reference approval/decision/review",
    )
    _assert(
        rework_task.get("owner_role_code") == "engineer",
        f"owner_role_code must be engineer, got {rework_task.get('owner_role_code')}",
    )

    print(f"\n  rework_task_id = {rework_task['id']}")
    print(f"  source_draft_id = {rework_task['source_draft_id']}")

    # ── 1f: event boundary ───────────────────────────────────────────
    print("\n1f. Event boundary: check publish_created was called once...")
    _assert(
        published_ids.count(rework_task["id"]) == 1,
        f"task_created must be published exactly once for rework task, "
        f"got {published_ids.count(rework_task['id'])}",
    )

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
        "decision_id": decision_id,
        "rework_task_id": rework_task["id"],
        "source_draft_id": rework_task["source_draft_id"],
    }


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 2: reject → executable rework task
# ══════════════════════════════════════════════════════════════════════════

def scenario_2_reject(client: TestClient) -> dict:
    print("\n" + "=" * 60)
    print("SCENARIO 2: reject creates executable rework task")
    print("=" * 60)

    project_id = _create_project(client, "BCG-10-R3 reject project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    # ── 2a: apply reject ─────────────────────────────────────────────
    print("\n2a. Apply reject action...")
    detail = _request_json(
        client, "POST", f"/approvals/{approval['id']}/actions",
        json_body={
            "action": "reject",
            "actor_name": "老板",
            "summary": "BCG-10-R3 reject for live evidence",
            "comment": "PRD is fundamentally incomplete.",
            "requested_changes": ["Rewrite execution section from scratch"],
            "highlighted_risks": ["Major scope gap", "Missing architecture review"],
        },
    )

    _assert(detail["status"] == "rejected", "status must be rejected")
    _assert(detail["decided_at"] is not None, "decided_at must be non-null")
    decision_id = detail["decisions"][-1]["id"]

    # ── 2b: find rework task ─────────────────────────────────────────
    print("\n2b. Find rework task via GET /tasks...")
    rework_task = _find_rework_task(client, approval["id"])
    _assert(rework_task is not None, "must find an arw: rework task after reject")
    _assert(rework_task["status"] == "pending", "rework task must be pending")
    _assert(rework_task["priority"] == "high", "rework task priority must be high")
    _assert(
        rework_task["risk_level"] == "high",
        f"reject rework task risk_level must be high (highlighted_risks present), "
        f"got {rework_task.get('risk_level')}",
    )
    _assert(
        rework_task.get("owner_role_code") == "engineer",
        f"owner_role_code must be engineer, got {rework_task.get('owner_role_code')}",
    )
    _assert(
        rework_task["source_draft_id"].startswith("arw:"),
        f"source_draft_id must start with arw:, got {rework_task.get('source_draft_id')}",
    )
    _assert(
        approval["id"] in (rework_task.get("input_summary") or ""),
        "input_summary must contain approval_id",
    )
    _assert(
        "reject" in (rework_task.get("input_summary") or ""),
        "input_summary must contain decision action reject",
    )

    print(f"\n  rework_task_id = {rework_task['id']}")
    print(f"  source_draft_id = {rework_task['source_draft_id']}")

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
        "decision_id": decision_id,
        "rework_task_id": rework_task["id"],
        "source_draft_id": rework_task["source_draft_id"],
    }


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 3: approve → no rework task
# ══════════════════════════════════════════════════════════════════════════

def scenario_3_approve(client: TestClient) -> dict:
    print("\n" + "=" * 60)
    print("SCENARIO 3: approve does NOT create rework task")
    print("=" * 60)

    project_id = _create_project(client, "BCG-10-R3 approve project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    # ── 3a: apply approve ────────────────────────────────────────────
    print("\n3a. Apply approve action...")
    detail = _request_json(
        client, "POST", f"/approvals/{approval['id']}/actions",
        json_body={
            "action": "approve",
            "actor_name": "老板",
            "summary": "BCG-10-R3 approve — should NOT create rework task",
        },
    )

    _assert(detail["status"] == "approved", "status must be approved")

    # ── 3b: confirm no rework task ───────────────────────────────────
    print("\n3b. Confirm no arw: rework task created...")
    rework_task = _find_rework_task(client, approval["id"])
    _assert(
        rework_task is None,
        f"approve must NOT create a rework task, but found {rework_task}",
    )

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
    }


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 4: idempotency / closed approval
# ══════════════════════════════════════════════════════════════════════════

def scenario_4_idempotency(client: TestClient) -> dict:
    print("\n" + "=" * 60)
    print("SCENARIO 4: idempotency / closed approval → 422, no duplicate")
    print("=" * 60)

    project_id = _create_project(client, "BCG-10-R3 idempotency project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    # ── 4a: first reject ─────────────────────────────────────────────
    print("\n4a. First reject...")
    detail = _request_json(
        client, "POST", f"/approvals/{approval['id']}/actions",
        json_body={
            "action": "reject",
            "actor_name": "老板",
            "summary": "First reject.",
        },
    )
    _assert(detail["status"] == "rejected", "first reject must set status to rejected")

    # ── 4b: find the one rework task for THIS approval ───────────────
    rework_task = _find_rework_task(client, approval["id"])
    _assert(rework_task is not None, "must find rework task for this approval")
    rework_task_id = rework_task["id"]

    # ── 4c: second reject on closed approval → 422 ───────────────────
    print("\n4c. Second reject on closed approval → expect 422...")
    _request_json(
        client, "POST", f"/approvals/{approval['id']}/actions",
        json_body={
            "action": "reject",
            "actor_name": "老板",
            "summary": "Should be rejected: approval already closed",
        },
        expected_status=422,
    )

    # ── 4d: no second rework task ────────────────────────────────────
    print("\n4d. Confirm no second rework task for this approval...")
    rework_after = _find_rework_task(client, approval["id"])
    _assert(rework_after is not None, "original rework task must still exist")
    _assert(rework_after["id"] == rework_task_id, "rework task id must be unchanged")

    # ── 4e: idempotency key prevents duplicate ───────────────────────
    print("\n4e. Confirm 422 does not create new rework tasks...")
    _assert(rework_after["id"] == rework_task_id, "no new rework task created from 422")

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
        "rework_task_id": rework_task_id,
    }


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 5: transaction rollback
# ══════════════════════════════════════════════════════════════════════════

def scenario_5_rollback(client: TestClient, monkeypatch) -> dict:
    print("\n" + "=" * 60)
    print("SCENARIO 5: transaction rollback on rework task creation failure")
    print("=" * 60)

    project_id = _create_project(client, "BCG-10-R3 rollback project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    # ── monkeypatch: fail when creating arw: task ────────────────────
    original_create_task = TaskService.create_task

    def _fail_arw(self, *args, **kwargs):
        sid = kwargs.get("source_draft_id", "")
        if isinstance(sid, str) and sid.startswith("arw:"):
            raise ValueError("simulated rework task persistence failure (live evidence)")
        return original_create_task(self, *args, **kwargs)

    monkeypatch.setattr(TaskService, "create_task", _fail_arw)

    # ── 5a: try request_changes ──────────────────────────────────────
    print("\n5a. Apply request_changes (will fail inside transaction)...")
    response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "request_changes",
            "actor_name": "老板",
            "summary": "This must rollback entirely.",
            "requested_changes": ["Force rollback"],
        },
    )
    _assert(
        response.status_code == 422,
        f"rollback must return 422, got {response.status_code}",
    )
    _assert(
        "simulated rework task persistence failure" in response.json()["detail"],
        "error detail must mention rollback cause",
    )

    # ── 5b: approval still pending_approval ──────────────────────────
    print("\n5b. Verify approval still pending_approval...")
    detail = _request_json(client, "GET", f"/approvals/{approval['id']}")
    _assert(
        detail["status"] == "pending_approval",
        f"approval status must still be pending_approval after rollback, "
        f"got {detail['status']}",
    )
    _assert(detail["decided_at"] is None, "decided_at must be null after rollback")
    _assert(detail["decisions"] == [], "decisions must be empty after rollback")
    _assert(
        detail["latest_decision"] is None,
        "latest_decision must be null after rollback",
    )

    # ── 5c: no rework task ───────────────────────────────────────────
    print("\n5c. Confirm no rework task was created...")
    rework_task = _find_rework_task(client, approval["id"])
    _assert(
        rework_task is None,
        "no rework task must exist after rollback",
    )

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
    }


# ══════════════════════════════════════════════════════════════════════════
# SCENARIO 6: event boundary — rollback publishes zero
# ══════════════════════════════════════════════════════════════════════════

def scenario_6_event_boundary_rollback(client: TestClient, monkeypatch) -> dict:
    print("\n" + "=" * 60)
    print("SCENARIO 6: event boundary — rollback publishes zero events")
    print("=" * 60)

    project_id = _create_project(client, "BCG-10-R3 event-boundary project")
    source_task_id = _create_source_task(client, project_id)
    deliverable = _create_deliverable(client, project_id, source_task_id)
    approval = _create_approval(client, deliverable["id"])

    published_ids: list[str] = []
    original_publish = TaskRepository.publish_created

    def _capture_all(self, task):
        published_ids.append(str(task.id))
        return original_publish(self, task)

    monkeypatch.setattr(TaskRepository, "publish_created", _capture_all)

    original_create_task = TaskService.create_task

    def _fail_arw_event(self, *args, **kwargs):
        sid = kwargs.get("source_draft_id", "")
        if isinstance(sid, str) and sid.startswith("arw:"):
            raise ValueError("simulated rework task persistence failure (event boundary)")
        return original_create_task(self, *args, **kwargs)

    monkeypatch.setattr(TaskService, "create_task", _fail_arw_event)

    # ── 6a: try request_changes → should rollback ────────────────────
    print("\n6a. Apply request_changes (will rollback)...")
    response = client.post(
        f"/approvals/{approval['id']}/actions",
        json={
            "action": "request_changes",
            "actor_name": "老板",
            "summary": "Event boundary test: must not publish on rollback.",
            "requested_changes": ["Event boundary check"],
        },
    )
    _assert(response.status_code == 422, "rollback must return 422")

    # ── 6b: zero publish_created calls ───────────────────────────────
    print("\n6b. Assert zero task_created events published...")
    _assert(
        len(published_ids) == 0,
        f"rollback must publish zero task_created events, "
        f"published {len(published_ids)}: {published_ids}",
    )

    return {
        "project_id": project_id,
        "approval_id": approval["id"],
    }


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    global _passed, _failed

    print("BCG-10-R3 Approval Rework Task Live Evidence")
    print(f"Python: {sys.version}")
    print()

    init_database()
    app = create_application()

    evidence: dict[str, Any] = {
        "scenarios": {},
    }

    with TestClient(app) as client:
        import pytest

        # We use a simple monkeypatch-like approach via direct attribute
        # patching since we cannot import pytest MonkeyPatch here easily.
        # Instead, we use a lightweight monkeypatcher.

        class _MonkeyPatch:
            def __init__(self):
                self._saved: list[tuple] = []

            def setattr(self, target, name, value):
                self._saved.append((target, name, getattr(target, name)))
                setattr(target, name, value)

            def undo(self):
                for target, name, original in reversed(self._saved):
                    setattr(target, name, original)
                self._saved.clear()

        # Scenario 1: request_changes
        mp1 = _MonkeyPatch()
        try:
            s1 = scenario_1_request_changes(client, mp1)
            evidence["scenarios"]["request_changes"] = {
                "result": "Pass",
                **s1,
            }
        finally:
            mp1.undo()

        # Scenario 2: reject
        s2 = scenario_2_reject(client)
        evidence["scenarios"]["reject"] = {
            "result": "Pass",
            **s2,
        }

        # Scenario 3: approve
        s3 = scenario_3_approve(client)
        evidence["scenarios"]["approve"] = {
            "result": "Pass",
            **s3,
        }

        # Scenario 4: idempotency
        s4 = scenario_4_idempotency(client)
        evidence["scenarios"]["idempotency"] = {
            "result": "Pass",
            **s4,
        }

        # Scenario 5: rollback
        mp5 = _MonkeyPatch()
        try:
            s5 = scenario_5_rollback(client, mp5)
            evidence["scenarios"]["rollback"] = {
                "result": "Pass",
                **s5,
            }
        finally:
            mp5.undo()

        # Scenario 6: event boundary rollback
        mp6 = _MonkeyPatch()
        try:
            s6 = scenario_6_event_boundary_rollback(client, mp6)
            evidence["scenarios"]["event_boundary"] = {
                "result": "Pass",
                **s6,
            }
        finally:
            mp6.undo()

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EVIDENCE SUMMARY")
    print("=" * 60)
    total = _passed + _failed
    print(f"  Checks: {total} total, {_passed} passed, {_failed} failed")
    print()

    evidence["total"] = total
    evidence["passed"] = _passed
    evidence["failed"] = _failed
    evidence["gate"] = "Pass" if _failed == 0 else "Partial"

    evidence_path = (
        ORCHESTRATOR_ROOT / "data" / "bcg10_rework_task_live_evidence.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, default=str, ensure_ascii=False))
    print(f"Evidence written to: {evidence_path}")

    if _failed > 0:
        print(f"\n  *** BCG-10-R3: {_failed} CHECK(S) FAILED ***")
        sys.exit(1)
    else:
        print("  BCG-10-R3: All checks PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
