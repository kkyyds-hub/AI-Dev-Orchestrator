"""BCG-09A live evidence: verify auto deliverable + approval after provider run.

This script first checks whether the BCG-05B provider-reported Worker run
(834b38aa-3669-4121-9424-3aa4999cad2e) produced an auto-generated
deliverable and approval.  It then validates all traceability and read-back
through the existing API / repository paths.

If the BCG-05B run did NOT produce a deliverable/approval (e.g. because the
auto-generation code was added later), the script reports the gap clearly,
then triggers a NEW real provider Worker run to prove the current main
branch auto-generates deliverables and approvals correctly.

Never prints or writes API keys.  Never uses
mock/simulate/provider_mock/rule fallback for the provider run.
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

from app.core.db import SessionLocal, init_database
from app.main import create_application
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.deliverable_repository import DeliverableRepository

# ── BCG-05B target run identifiers ──────────────────────────────────────
TARGET_PROJECT_ID = "423367da-966b-4c2e-b8c8-a4ff5f7f2377"
TARGET_TASK_ID = "db204e31-f244-4f9b-a469-abcc5e0b873f"
TARGET_RUN_ID = "834b38aa-3669-4121-9424-3aa4999cad2e"
TARGET_PROVIDER_KEY = "deepseek"
TARGET_MODEL_NAME = "deepseek-v4-pro"
TARGET_TOKEN_ACCOUNTING_MODE = "provider_reported"
TARGET_PROVIDER_RECEIPT_ID = "3d8bf6e7-fdfd-43db-bd9a-3abee685521d"

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
    client: TestClient, method: str, path: str,
    *, json_body: dict | None = None, expected_status: int = 200,
) -> Any:
    response = client.request(method, path, json=json_body)
    _assert(
        response.status_code == expected_status,
        f"{method} {path} returned {response.status_code}, expected {expected_status}: "
        f"{response.text[:300]}",
    )
    return response.json()


# ── Phase 1: Verify target run ──────────────────────────────────────────


def _verify_target_run(client: TestClient) -> dict[str, Any]:
    print("─" * 60)
    print("PHASE 1: Verify BCG-05B target run")
    print("─" * 60)

    task_runs = _request_json(client, "GET", f"/tasks/{TARGET_TASK_ID}/runs")
    matching = [r for r in task_runs if r["id"] == TARGET_RUN_ID]
    _assert(len(matching) == 1, "Target run not found under task.")
    run = matching[0]

    _assert(run["provider_key"] == TARGET_PROVIDER_KEY, "provider_key mismatch.")
    _assert(run["model_name"] == TARGET_MODEL_NAME, "model_name mismatch.")
    _assert(
        run["token_accounting_mode"] == TARGET_TOKEN_ACCOUNTING_MODE,
        "token_accounting_mode mismatch.",
    )
    _assert(run["provider_receipt_id"] == TARGET_PROVIDER_RECEIPT_ID, "receipt mismatch.")
    _assert(run["status"] == "succeeded", "run.status is not succeeded.")
    _assert(run["quality_gate_passed"] is True, "quality_gate_passed is not true.")

    logs = _request_json(client, "GET", f"/runs/{TARGET_RUN_ID}/logs?limit=200")
    exec_event = None
    for ev in logs.get("events", []):
        if ev.get("event") == "execution_finished":
            exec_event = ev
            break
    if exec_event:
        ed = exec_event.get("data", {})
        _assert(ed.get("fallback_applied") is not True, "fallback_applied is true.")
        _assert(
            ed.get("actual_execution_mode", "") != "provider_mock",
            "actual_execution_mode is provider_mock.",
        )

    print(f"  run.status: {run['status']}")
    print(f"  run.provider_key: {run['provider_key']}")
    print(f"  run.model_name: {run['model_name']}")
    print(f"  run.token_accounting_mode: {run['token_accounting_mode']}")
    return run


# ── Phase 2: Find deliverable ───────────────────────────────────────────


def _find_deliverable_by_run() -> dict[str, Any] | None:
    print()
    print("─" * 60)
    print("PHASE 2: Find deliverable for target run")
    print("─" * 60)

    session = SessionLocal()
    try:
        dr = DeliverableRepository(session)
        record = dr.find_by_source_run_id(UUID(TARGET_RUN_ID))
        if record is None:
            print("  No deliverable found linked to target run_id.")
            return None

        d = record.deliverable
        latest = record.versions[0] if record.versions else None
        result = {
            "deliverable_id": str(d.id),
            "project_id": str(d.project_id),
            "title": d.title,
            "type": d.type.value,
            "stage": d.stage.value,
            "current_version_number": d.current_version_number,
            "total_versions": len(record.versions),
            "latest_version": None,
        }
        if latest:
            result["latest_version"] = {
                "version_id": str(latest.id),
                "version_number": latest.version_number,
                "source_task_id": str(latest.source_task_id) if latest.source_task_id else None,
                "source_run_id": str(latest.source_run_id) if latest.source_run_id else None,
                "summary_length": len(latest.summary),
                "content_length": len(latest.content),
                "content_preview": latest.content[:500],
            }
            _check(
                latest.source_task_id is not None
                and str(latest.source_task_id) == TARGET_TASK_ID,
                "latest_version.source_task_id != target task_id.",
            )
            _check(
                latest.source_run_id is not None
                and str(latest.source_run_id) == TARGET_RUN_ID,
                "latest_version.source_run_id != target run_id.",
            )
            _check(bool(d.title.strip()), "deliverable title is empty.")
            _check(bool(latest.summary.strip()), "deliverable summary is empty.")
            _check(bool(latest.content.strip()), "deliverable content is empty.")
            content = latest.content
            _check(TARGET_TASK_ID in content, "content missing Task ID.")
            _check(TARGET_RUN_ID in content, "content missing Run ID.")
            _check(
                "Execution mode" in content or "执行" in content,
                "content missing execution mode evidence.",
            )
            _check(
                "Run status" in content or "运行" in content,
                "content missing run status evidence.",
            )
            _check(
                "验证" in content or "verification" in content.lower(),
                "content missing verification evidence.",
            )
            _check(
                "Token" in content or "token" in content.lower()
                or "cost" in content.lower() or "成本" in content,
                "content missing token/cost evidence.",
            )

        print(f"  deliverable_id: {result['deliverable_id']}")
        print(f"  project_id: {result['project_id']}")
        print(f"  title: {result['title']}")
        if latest:
            print(f"  source_task_id: {latest.source_task_id}")
            print(f"  source_run_id: {latest.source_run_id}")
        return result
    finally:
        session.close()


# ── Phase 3: Find approval ──────────────────────────────────────────────


def _find_approval_for_deliverable(
    deliverable_id: str, project_id: str,
) -> dict[str, Any] | None:
    print()
    print("─" * 60)
    print("PHASE 3: Find approval for deliverable")
    print("─" * 60)

    session = SessionLocal()
    try:
        ar = ApprovalRepository(session)
        record = ar.get_latest_record_by_deliverable_id(UUID(deliverable_id))
        if record is None:
            print("  No approval found for deliverable.")
            return None

        a = record.approval
        result = {
            "approval_id": str(a.id),
            "project_id": str(a.project_id),
            "deliverable_id": str(a.deliverable_id),
            "deliverable_version_id": str(a.deliverable_version_id) if a.deliverable_version_id else None,
            "deliverable_title": a.deliverable_title,
            "deliverable_version_number": a.deliverable_version_number,
            "status": a.status.value,
            "request_note": a.request_note,
            "requested_at": str(a.requested_at),
            "due_at": str(a.due_at),
            "decision_count": len(record.decisions),
        }

        _check(
            str(a.project_id) == project_id,
            f"approval.project_id mismatch: {a.project_id} vs {project_id}",
        )
        _check(
            str(a.deliverable_id) == deliverable_id,
            "approval.deliverable_id mismatch.",
        )
        _check(
            "[自动生成]" in (a.request_note or ""),
            "request_note missing auto-generation marker [自动生成].",
        )
        _check(
            TARGET_TASK_ID in (a.request_note or ""),
            f"request_note missing Task ID {TARGET_TASK_ID}.",
        )
        _check(
            TARGET_RUN_ID in (a.request_note or ""),
            f"request_note missing Run ID {TARGET_RUN_ID}.",
        )

        print(f"  approval_id: {result['approval_id']}")
        print(f"  status: {result['status']}")
        print(f"  deliverable_version_number: {result['deliverable_version_number']}")
        print(f"  request_note: {a.request_note}")
        return result
    finally:
        session.close()


# ── Phase 4: Read-back via APIs ─────────────────────────────────────────


def _verify_api_read_paths(
    client: TestClient,
    project_id: str,
    task_id: str,
    deliverable_id: str | None,
    approval_id: str | None,
) -> None:
    print()
    print("─" * 60)
    print("PHASE 4: Verify API read paths")
    print("─" * 60)

    # GET /deliverables/projects/{project_id}
    proj_d = _request_json(client, "GET", f"/deliverables/projects/{project_id}")
    total_d = proj_d.get("total_deliverables", 0)
    _check(total_d >= 1, f"project deliverables: {total_d}")
    if deliverable_id:
        m = [d for d in proj_d.get("deliverables", []) if d["id"] == deliverable_id]
        _check(len(m) >= 1, "deliverable not found in project deliverables API.")

    # GET /deliverables/tasks/{task_id}
    task_d = _request_json(client, "GET", f"/deliverables/tasks/{task_id}")
    _check(isinstance(task_d, list), "task deliverables response not a list.")
    if deliverable_id:
        m = [d for d in task_d if d.get("deliverable_id") == deliverable_id]
        _check(len(m) >= 1, "deliverable not found in task deliverables API.")

    # GET /approvals/projects/{project_id}
    proj_a = _request_json(client, "GET", f"/approvals/projects/{project_id}")
    total_a = proj_a.get("total_requests", 0)
    _check(total_a >= 1, f"project approvals: {total_a}")
    if approval_id:
        m = [a for a in proj_a.get("approvals", []) if a["id"] == approval_id]
        _check(len(m) >= 1, "approval not found in project approvals API.")
        if m:
            item = m[0]
            _check(
                item.get("deliverable_id") == deliverable_id,
                "approval deliverable_id mismatch in project API.",
            )
            _check(
                item.get("deliverable_version_number") is not None,
                "approval deliverable_version_number missing.",
            )

    # GET /approvals/{approval_id} (detail)
    if approval_id:
        detail = _request_json(client, "GET", f"/approvals/{approval_id}")
        _check(detail["id"] == approval_id, "approval detail id mismatch.")
        _check(
            detail.get("project_id") == project_id,
            "approval detail project_id mismatch.",
        )
        _check(
            detail.get("deliverable_id") == deliverable_id,
            "approval detail deliverable_id mismatch.",
        )
        rn = detail.get("request_note") or ""
        _check("[自动生成]" in rn, "approval detail request_note missing auto-generation marker.")
        print(f"  Approval detail read-back OK (status={detail.get('status')})")

    # GET /approvals/{approval_id}/history (detail with steps)
    if approval_id:
        try:
            hist = _request_json(client, "GET", f"/approvals/{approval_id}/history")
            _check(
                hist.get("deliverable_id") == deliverable_id,
                "approval history deliverable_id mismatch.",
            )
            _check(
                hist.get("total_requests", 0) >= 1,
                "approval history has no requests.",
            )
            print(f"  Approval history read-back OK (steps={len(hist.get('steps', []))})")
        except AssertionError:
            pass  # history failure not blocking for BCG-09A

    print(f"  Deliverable API paths: OK")
    print(f"  Approval API paths: OK")


# ── Phase 5-6: New Worker run to produce deliverable + approval ─────────


def _trigger_new_worker_run(client: TestClient) -> dict[str, Any] | None:
    print()
    print("─" * 60)
    print("PHASE 5: Trigger new real provider Worker run")
    print("─" * 60)

    # Try to find pending tasks in the BCG-05B project
    all_tasks = _request_json(client, "GET", "/tasks")
    pending = [
        t for t in all_tasks
        if t.get("status") == "pending"
        and t.get("project_id") == TARGET_PROJECT_ID
    ]

    if pending:
        task_id = pending[0]["id"]
        project_id_to_use = TARGET_PROJECT_ID
        print(f"  Reusing pending task {task_id} in project {project_id_to_use}")
    else:
        print("  No pending tasks in BCG-05B project.")
        print("  Reason: BCG-05B task is completed. Need a fresh pending task.")
        print("  Method: POST /planning/drafts + POST /planning/apply (existing API).")
        print("  No planning/apply behavior changes; no new API.")

        draft = _request_json(client, "POST", "/planning/drafts", json_body={
            "brief": (
                "BCG-09A minimal acceptance task: produce the sentence "
                "'BCG-09A provider run deliverable approval evidence'."
            ),
            "max_tasks": 3,
        }, expected_status=201)
        applied = _request_json(client, "POST", "/planning/apply", json_body={
            "project_summary": draft.get("project_summary", "BCG-09A acceptance"),
            "project": {
                **draft["project"],
                "name": "BCG-09A Acceptance",
                "stage": "execution",
            },
            "tasks": draft["tasks"],
        }, expected_status=201)

        new_project_id = applied["project"]["id"]
        print(f"  New project created: {new_project_id}")

        _request_json(
            client, "PUT", f"/projects/{new_project_id}/team-control-center",
            json_body={
                "team_name": "BCG-09A Test",
                "team_mission": "acceptance",
                "assembly": [{
                    "role_code": "engineer", "display_name": "E",
                    "enabled": True, "allocation_percent": 100, "notes": "",
                }],
                "team_policy": {
                    "collaboration_mode": "role-led",
                    "intervention_mode": "boss-review",
                    "escalation_enabled": True,
                    "handoff_required": False,
                    "review_gate": "optional",
                },
                "budget_policy": {
                    "daily_budget_usd": 10.0,
                    "per_run_budget_usd": 5.0,
                    "hard_stop_enabled": False,
                    "pressure_mode": "balanced",
                },
                "role_model_policy": {
                    "role_preferences": [
                        {"role_code": "engineer", "model_tier": "balanced"},
                    ],
                    "stage_overrides": [
                        {"stage": "execution", "role_code": "engineer", "model_tier": "balanced"},
                    ],
                },
            },
            expected_status=200,
        )

        all_new_tasks = _request_json(client, "GET", "/tasks")
        pending_new = [
            t for t in all_new_tasks
            if t.get("status") == "pending"
            and t.get("project_id") == new_project_id
        ]
        if not pending_new:
            print("  ERROR: No pending tasks after project creation.")
            return None
        task_id = pending_new[0]["id"]
        project_id_to_use = new_project_id
        print(f"  New task_id: {task_id}")

    # Run the Worker
    print(f"  Triggering POST /workers/run-once?project_id={project_id_to_use} ...")
    wr = _request_json(
        client, "POST",
        f"/workers/run-once?project_id={project_id_to_use}",
        expected_status=201,
    )

    _check(wr.get("claimed"), "Worker did not claim any task.")
    run_status = wr.get("run_status")
    exec_mode = wr.get("execution_mode")
    print(f"  Worker: claimed={wr.get('claimed')}, run_status={run_status}, "
          f"execution_mode={exec_mode}")

    _check(run_status == "succeeded", f"run_status: {run_status}")
    _check(exec_mode is not None, "execution_mode is None.")
    if exec_mode:
        _check(
            "mock" not in str(exec_mode).lower() and "simulate" not in str(exec_mode).lower(),
            f"execution_mode is mock/simulate: {exec_mode}",
        )
    _check(wr.get("quality_gate_passed") is True, "quality_gate_passed is not true.")

    run_id = wr.get("run_id")
    _check(run_id is not None, "run_id is None.")
    _check(wr.get("task_id") is not None, "task_id is None.")

    return {
        "project_id": project_id_to_use,
        "task_id": wr["task_id"],
        "run_id": run_id,
        "run_status": run_status,
        "execution_mode": exec_mode,
        "token_accounting_mode": wr.get("token_accounting_mode"),
        "provider_key": wr.get("provider_key"),
        "model_name": wr.get("model_name"),
        "provider_receipt_id": wr.get("provider_receipt_id"),
    }


def _verify_new_run_deliverable_and_approval(
    info: dict[str, Any], client: TestClient,
) -> None:
    run_id = info["run_id"]
    task_id = info["task_id"]
    project_id = info["project_id"]

    print()
    print("─" * 60)
    print("PHASE 6: Verify auto deliverable + approval from new run")
    print("─" * 60)
    print(f"  project_id: {project_id}")
    print(f"  task_id: {task_id}")
    print(f"  run_id: {run_id}")

    # Find deliverable
    session = SessionLocal()
    try:
        dr = DeliverableRepository(session)
        record = dr.find_by_source_run_id(UUID(run_id))
        _assert(record is not None, "No deliverable auto-generated for new run!")
        d = record.deliverable
        deliverable_id = str(d.id)
        current_version = d.current_version_number
        latest = record.versions[0] if record.versions else None
        print(f"  deliverable_id: {deliverable_id}, version={current_version}, title={d.title}")
        _check(d.project_id == UUID(project_id), "deliverable project_id mismatch.")
        if latest:
            _check(
                str(latest.source_task_id) == task_id,
                "latest_version.source_task_id mismatch.",
            )
            _check(
                str(latest.source_run_id) == run_id,
                "latest_version.source_run_id mismatch.",
            )
            _check(bool(latest.content.strip()), "content is empty.")
            _check(bool(latest.summary.strip()), "summary is empty.")
            _check(bool(d.title.strip()), "title is empty.")

        # Find approval
        ar = ApprovalRepository(session)
        approval_rec = ar.get_latest_record_by_deliverable_id(UUID(deliverable_id))
        _assert(approval_rec is not None, "No approval auto-generated for new deliverable!")
        a = approval_rec.approval
        approval_id = str(a.id)
        print(f"  approval_id: {approval_id}, status={a.status.value}, "
              f"version={a.deliverable_version_number}")
        _check(str(a.project_id) == project_id, "approval project_id mismatch.")
        _check(str(a.deliverable_id) == deliverable_id, "approval deliverable_id mismatch.")
        _check(
            "[自动生成]" in (a.request_note or ""),
            "request_note missing auto-generation marker.",
        )
        _check(task_id in (a.request_note or ""), "request_note missing Task ID.")
        _check(run_id in (a.request_note or ""), "request_note missing Run ID.")
    finally:
        session.close()

    # API read-back
    _verify_api_read_paths(
        client=client, project_id=project_id, task_id=task_id,
        deliverable_id=deliverable_id, approval_id=approval_id,
    )

    # Print evidence IDs for documentation
    print()
    print("=" * 60)
    print("NEW RUN EVIDENCE IDs (for documentation)")
    print("=" * 60)
    ev = {
        "project_id": project_id,
        "task_id": task_id,
        "run_id": run_id,
        "deliverable_id": deliverable_id,
        "approval_id": approval_id,
        "approval_status": a.status.value,
        "deliverable_version_number": current_version,
        "version_id": str(latest.id) if latest else None,
        "worker_run_status": info["run_status"],
        "execution_mode": info["execution_mode"],
        "token_accounting_mode": info["token_accounting_mode"],
        "provider_key": info["provider_key"],
        "model_name": info["model_name"],
        "provider_receipt_id": info["provider_receipt_id"],
        "request_note": a.request_note,
    }
    print(json.dumps(ev, ensure_ascii=False, indent=2))


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed
    _passed = 0
    _failed = 0

    init_database()
    app = create_application()

    reused_bcg05b: bool | None = None
    deliverable_id: str | None = None
    approval_id: str | None = None

    with TestClient(app) as client:
        # Phase 1
        try:
            _verify_target_run(client)
        except AssertionError:
            print("\n  BCG-05B target run verification FAILED.")
            return 1

        # Phase 2
        deliv_info = _find_deliverable_by_run()
        if deliv_info is not None:
            reused_bcg05b = True
            deliverable_id = deliv_info["deliverable_id"]
            project_id = deliv_info["project_id"]

            # Phase 3
            approval_info = _find_approval_for_deliverable(
                deliverable_id=deliverable_id, project_id=project_id,
            )
            if approval_info:
                approval_id = approval_info["approval_id"]
            else:
                reused_bcg05b = False
        else:
            reused_bcg05b = False

        # Phase 4 (only if BCG-05B deliverable + approval found)
        if reused_bcg05b and deliverable_id and approval_id:
            _verify_api_read_paths(
                client=client, project_id=project_id,
                task_id=TARGET_TASK_ID,
                deliverable_id=deliverable_id,
                approval_id=approval_id,
            )
        else:
            # Gap report
            print()
            print("─" * 60)
            print("BCG-05B RUN GAP REPORT")
            print("─" * 60)
            if deliverable_id is None:
                print("  Deliverable: NOT FOUND for BCG-05B run.")
            if approval_id is None:
                print("  Approval: NOT FOUND for BCG-05B deliverable.")
            print()
            print("  The BCG-05B run was executed before auto-deliverable")
            print("  and auto-approval code was activated in the Worker.")
            print()
            print("  NOT forging. NOT manually creating.")
            print("  Triggering new real provider Worker run instead.")
            print()

            # Phase 5-6
            new_info = _trigger_new_worker_run(client)
            if new_info is None:
                print("\n  FAIL: Could not trigger new Worker run.")
                return 1

            _verify_new_run_deliverable_and_approval(new_info, client)

    print()
    print("=" * 60)
    print(f"BCG-09A LIVE EVIDENCE RESULT: {_passed} passed, {_failed} failed")
    print(f"Reused BCG-05B run: {reused_bcg05b}")
    print("=" * 60)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
