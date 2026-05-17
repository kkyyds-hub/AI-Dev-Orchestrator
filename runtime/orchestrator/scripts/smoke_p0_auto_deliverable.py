"""P0-1 smoke: verify auto-generate deliverable on successful worker run.

All guard scenarios are verified by calling the real
``_auto_create_run_deliverable()`` against a real database — no
guard-logic replication.
"""

from __future__ import annotations

import json, os, shutil, stat, sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "smoke-p0-auto-deliverable"
SMOKE_RUNTIME_DATA = SMOKE_ROOT / "runtime-data"
REAL_CONFIG_PATH = (
    RUNTIME_ROOT.parent / "data" / "provider-settings" / "openai-provider-config.json"
)


def _remove_readonly(f, p, _):
    Path(p).chmod(stat.S_IWRITE)
    f(p)


def setup():
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)
    SMOKE_RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
    (SMOKE_RUNTIME_DATA / "db").mkdir(exist_ok=True)
    (SMOKE_RUNTIME_DATA / "provider-settings").mkdir(exist_ok=True)
    if REAL_CONFIG_PATH.exists():
        rc = json.loads(REAL_CONFIG_PATH.read_text(encoding="utf-8"))
        (
            SMOKE_RUNTIME_DATA / "provider-settings" / "openai-provider-config.json"
        ).write_text(json.dumps(rc, ensure_ascii=False), encoding="utf-8")
    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ROOT / "workspaces")
    os.environ["DAILY_BUDGET_USD"] = "10.00"
    os.environ["SESSION_BUDGET_USD"] = "10.00"


# -- Minimal execution / verification types that duck-type the real ones --


@dataclass
class FakeExecution:
    success: bool
    summary: str
    mode: str = "simulate"


@dataclass
class FakeVerification:
    success: bool
    quality_gate_passed: bool
    summary: str = ""
    mode: str = "simulate"


def _deliverable_count_for_project(project_id: UUID) -> int:
    """Return the number of deliverables linked to *project_id*."""
    from app.core.db import SessionLocal
    from app.repositories.deliverable_repository import DeliverableRepository

    session = SessionLocal()
    try:
        return len(DeliverableRepository(session).list_records_by_project_id(project_id))
    finally:
        session.close()


def _find_deliverable_by_source_run(source_run_id: UUID):
    """Return a deliverable record linked to *source_run_id*, or None."""
    from app.core.db import SessionLocal
    from app.repositories.deliverable_repository import DeliverableRepository

    session = SessionLocal()
    try:
        return DeliverableRepository(session).find_by_source_run_id(source_run_id)
    finally:
        session.close()


# ---------------------------------------------------------------------------


def main() -> int:
    setup()

    passed = 0
    failed = 0

    def check(condition: bool, label: str) -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {label}")
        else:
            failed += 1
            print(f"  FAIL: {label}")

    # -- Phase 0: import & truncation unit tests --------------------------
    print("=" * 60)
    print("PHASE 0: truncation helpers (unit)")
    print("=" * 60)

    from app.workers.task_worker import (
        _auto_create_run_deliverable,
        _truncate_deliverable_text,
        _DELIVERABLE_TITLE_MAX,
        _DELIVERABLE_SUMMARY_MAX,
        _DELIVERABLE_CONTENT_MAX,
    )

    check(_truncate_deliverable_text("hello", 100) == "hello", "short preserved")
    long_t = _truncate_deliverable_text("x" * (_DELIVERABLE_TITLE_MAX + 50), _DELIVERABLE_TITLE_MAX)
    check(len(long_t) <= _DELIVERABLE_TITLE_MAX and long_t.endswith("..."), "long truncated")
    check(_truncate_deliverable_text("   ", 100) == "Worker run completed successfully.", "empty fallback")
    content_trunc = _truncate_deliverable_text("A" * (_DELIVERABLE_CONTENT_MAX + 1000), _DELIVERABLE_CONTENT_MAX)
    check(len(content_trunc) <= _DELIVERABLE_CONTENT_MAX, f"content max ({len(content_trunc)})")

    # -- Phase 1: create project + task via TestClient --------------------
    print()
    print("=" * 60)
    print("PHASE 1: create test project + real worker run")
    print("=" * 60)

    from fastapi.testclient import TestClient
    from app.core.db import init_database, SessionLocal
    from app.main import create_application

    init_database()
    app = create_application()

    with TestClient(app) as client:
        draft = client.post("/planning/drafts", json={
            "brief": "最小任务：返回 hello world",
            "max_tasks": 3,
        }).json()
        ar = client.post("/planning/apply", json={
            "project_summary": draft.get("project_summary", "test"),
            "project": {**draft["project"], "name": "P0-1 Smoke", "stage": "execution"},
            "tasks": draft["tasks"],
        }).json()
        project_id_str = ar["project"]["id"]
        project_id = UUID(project_id_str)
        print(f"  project_id: {project_id}")

        client.put(f"/projects/{project_id}/team-control-center", json={
            "team_name": "P0-1 Test",
            "team_mission": "test",
            "assembly": [{"role_code": "engineer", "display_name": "E", "enabled": True, "allocation_percent": 100, "notes": ""}],
            "team_policy": {"collaboration_mode": "role-led", "intervention_mode": "boss-review", "escalation_enabled": True, "handoff_required": False, "review_gate": "optional"},
            "budget_policy": {"daily_budget_usd": 10.0, "per_run_budget_usd": 5.0, "hard_stop_enabled": False, "pressure_mode": "balanced"},
            "role_model_policy": {
                "role_preferences": [{"role_code": "engineer", "model_tier": "balanced"}],
                "stage_overrides": [{"stage": "execution", "role_code": "engineer", "model_tier": "balanced"}],
            },
        })

        wr = client.post(f"/workers/run-once?project_id={project_id}").json()
        rs = wr.get("run_status")
        print(f"  worker run_status: {rs}")
        check(rs == "succeeded", f"real worker run succeeded (got {rs})")

        dr = client.get(f"/deliverables/projects/{project_id}").json()
        total = dr.get("total_deliverables", 0)
        print(f"  deliverable count after run: {total}")
        check(total >= 1, f"deliverable auto-generated (total={total})")

        if dr.get("deliverables"):
            d = dr["deliverables"][0]
            lv = d.get("latest_version", {})
            check(bool(lv.get("source_task_id")), "source_task_id present")
            check(bool(lv.get("source_run_id")), "source_run_id present")
            check(not str(lv.get("source_run_id", "")).startswith("mock-"), "source_run_id not mock-")

    # -- Phase 2: get a real completed task + run for guard tests --------
    print()
    print("=" * 60)
    print("PHASE 2: build real worker for direct guard tests")
    print("=" * 60)

    from app.workers.task_worker import build_task_worker
    from app.repositories.task_repository import TaskRepository
    from app.repositories.run_repository import RunRepository

    worker_session = SessionLocal()
    worker = build_task_worker(session=worker_session)
    check(worker.deliverable_service is not None, "worker has deliverable_service")

    task_repo = TaskRepository(worker_session)
    tasks = task_repo.list_by_project_id(project_id)
    completed_tasks = [t for t in tasks if t.status.value == "completed"]
    check(len(completed_tasks) >= 1, f"at least one completed task (found {len(completed_tasks)})")

    base_task = completed_tasks[0]
    run_repo = RunRepository(worker_session)
    base_runs = run_repo.list_by_task_id(base_task.id)
    check(len(base_runs) >= 1, f"at least one run for completed task (found {len(base_runs)})")
    base_run = base_runs[0]

    from app.domain.run import RunStatus
    from app.domain.task import TaskStatus

    print(f"  task={base_task.id} status={base_task.status.value}")
    print(f"  run={base_run.id} status={base_run.status.value}")

    # -- Phase 3: guard matrix — REAL calls to _auto_create ---------------
    print()
    print("=" * 60)
    print("PHASE 3: guard matrix (real _auto_create calls)")
    print("=" * 60)

    base_count = _deliverable_count_for_project(project_id)
    print(f"  baseline deliverable count: {base_count}")

    from app.domain.run import Run
    from app.domain.task import Task

    def new_test_run(run_id: UUID, status: RunStatus = RunStatus.SUCCEEDED) -> Run:
        """Create a fresh Run row in the DB for one guard test case."""
        return run_repo.create_running_run(
            task_id=base_task.id,
            owner_role_code="engineer",
        )

    def finish_test_run(run: Run, status: RunStatus) -> Run:
        return run_repo.finish_run(
            run_id=run.id,
            status=status,
            result_summary="test run for guard check",
            provider_key="deepseek",
            prompt_template_key="test",
            prompt_template_version="0.1.0",
            prompt_char_count=0,
            token_accounting_mode="provider_reported",
            total_tokens=0,
            estimated_cost=0.0,
            prompt_tokens=0,
            completion_tokens=0,
        )

    # ── Guard: execution.success=False → NO deliverable ────────────
    def _make_run_and_test(label: str, exec: FakeExecution, ver: FakeVerification | None, expect_generated: bool) -> None:
        new_run = run_repo.create_running_run(task_id=base_task.id, owner_role_code="engineer")
        new_run = run_repo.finish_run(
            run_id=new_run.id, status=RunStatus.SUCCEEDED if exec.success else RunStatus.FAILED,
            result_summary="guard-test", provider_key="deepseek", prompt_template_key="test",
            prompt_template_version="0.1", prompt_char_count=5,
            token_accounting_mode="provider_reported", total_tokens=10,
            estimated_cost=0.0, prompt_tokens=5, completion_tokens=5,
        )
        worker_session.commit()

        run_id_before = new_run.id
        found_before = _find_deliverable_by_source_run(run_id_before)
        assert found_before is None, f"Unexpected pre-existing deliverable for {run_id_before}"

        _auto_create_run_deliverable(
            worker=worker, task=base_task, run=new_run,
            execution=exec, verification=ver,
        )
        worker_session.commit()

        found_after = _find_deliverable_by_source_run(run_id_before)
        if expect_generated:
            check(found_after is not None, f"{label}: deliverable created")
        else:
            check(found_after is None, f"{label}: NO deliverable created")

    # 1. exec.success=False, no verification
    _make_run_and_test("exec_fail", FakeExecution(success=False, summary="fail"), None, False)
    # 2. exec.success=True, no verification → generates
    _make_run_and_test("exec_ok_no_ver", FakeExecution(success=True, summary="ok"), None, True)
    # 3. exec.success=True, ver.success=True, qg=True → generates
    _make_run_and_test("exec_ok_ver_ok_qg_ok", FakeExecution(success=True, summary="ok"), FakeVerification(success=True, quality_gate_passed=True, summary="v"), True)
    # 4. exec.success=True, ver.success=False, qg=True → NO generate
    _make_run_and_test("ver_fail_qg_ok", FakeExecution(success=True, summary="ok"), FakeVerification(success=False, quality_gate_passed=True, summary="v"), False)
    # 5. exec.success=True, ver.success=True, qg=False → NO generate
    _make_run_and_test("ver_ok_qg_fail", FakeExecution(success=True, summary="ok"), FakeVerification(success=True, quality_gate_passed=False, summary="v"), False)
    # 6. exec.success=True, ver.success=False, qg=False → NO generate
    _make_run_and_test("ver_fail_qg_fail", FakeExecution(success=True, summary="ok"), FakeVerification(success=False, quality_gate_passed=False, summary="v"), False)

    # -- Phase 4: idempotency — call twice with SAME run_id -------------
    print()
    print("=" * 60)
    print("PHASE 4: idempotency")
    print("=" * 60)

    idem_run = run_repo.create_running_run(task_id=base_task.id, owner_role_code="engineer")
    idem_run = run_repo.finish_run(
        run_id=idem_run.id, status=RunStatus.SUCCEEDED, result_summary="idem-test",
        provider_key="deepseek", prompt_template_key="test", prompt_template_version="0.1",
        prompt_char_count=5, token_accounting_mode="provider_reported", total_tokens=10,
        estimated_cost=0.0, prompt_tokens=5, completion_tokens=5,
    )
    worker_session.commit()

    count_before = _deliverable_count_for_project(project_id)
    found_before = _find_deliverable_by_source_run(idem_run.id)
    check(found_before is None, "no deliverable yet for idem run")

    # Call 1 — should create
    _auto_create_run_deliverable(
        worker=worker, task=base_task, run=idem_run,
        execution=FakeExecution(success=True, summary="call-1"), verification=None,
    )
    worker_session.commit()
    after_first = _deliverable_count_for_project(project_id)
    check(after_first == count_before + 1, f"first call creates deliverable ({count_before} -> {after_first})")

    # Call 2 — should SKIP (idempotent)
    _auto_create_run_deliverable(
        worker=worker, task=base_task, run=idem_run,
        execution=FakeExecution(success=True, summary="call-2"), verification=None,
    )
    worker_session.commit()
    after_second = _deliverable_count_for_project(project_id)
    check(after_second == after_first, f"second call skips (still {after_first})")

    found_after = _find_deliverable_by_source_run(idem_run.id)
    check(found_after is not None, "deliverable exists after idempotent calls")

    # -- Phase 5: long text — call with oversized title/summary ----------
    print()
    print("=" * 60)
    print("PHASE 5: long text truncation (real call)")
    print("=" * 60)

    long_run = run_repo.create_running_run(task_id=base_task.id, owner_role_code="engineer")
    long_run = run_repo.finish_run(
        run_id=long_run.id, status=RunStatus.SUCCEEDED, result_summary="long-test",
        provider_key="deepseek", prompt_template_key="test", prompt_template_version="0.1",
        prompt_char_count=5, token_accounting_mode="provider_reported", total_tokens=10,
        estimated_cost=0.0, prompt_tokens=5, completion_tokens=5,
    )
    # Use a task with a very long title for the long-text test
    long_task = base_task  # existing task, title may be short — we test summary mostly
    worker_session.commit()

    huge_summary = "X" * (_DELIVERABLE_SUMMARY_MAX + 500)
    huge_content = "C" * (_DELIVERABLE_CONTENT_MAX + 5000)

    _auto_create_run_deliverable(
        worker=worker, task=long_task, run=long_run,
        execution=FakeExecution(success=True, summary=huge_summary), verification=None,
    )
    worker_session.commit()

    long_deliv = _find_deliverable_by_source_run(long_run.id)
    check(long_deliv is not None, "long-text deliverable created (did not crash)")

    if long_deliv:
        latest = long_deliv.versions[0] if long_deliv.versions else None
        if latest:
            check(len(latest.summary) <= _DELIVERABLE_SUMMARY_MAX,
                  f"summary truncated ({len(latest.summary)} <= {_DELIVERABLE_SUMMARY_MAX})")
            check(len(latest.content) <= _DELIVERABLE_CONTENT_MAX,
                  f"content truncated ({len(latest.content)} <= {_DELIVERABLE_CONTENT_MAX})")

    # -- Phase 6: P0-2 — approval auto-generation --------------------
    print()
    print("=" * 60)
    print("PHASE 6: P0-2 — auto approval request")
    print("=" * 60)

    from app.workers.task_worker import _auto_create_run_approval

    # 6a: existing deliverable (from guard test run that generated) → create approval
    # Find a guard-test deliverable that doesn't have an approval yet
    deliverable_session = SessionLocal()
    from app.repositories.deliverable_repository import DeliverableRepository
    from app.repositories.approval_repository import ApprovalRepository
    dr = DeliverableRepository(deliverable_session)
    ar = ApprovalRepository(deliverable_session)
    all_delivs = dr.list_records_by_project_id(project_id)
    print(f"  total deliverables in project: {len(all_delivs)}")

    # Find a deliverable without approval
    target_deliv = None
    for d in all_delivs:
        existing_approval = ar.get_latest_record_by_deliverable_id(d.deliverable.id)
        if existing_approval is None:
            target_deliv = d
            break

    check(target_deliv is not None, f"found deliverable without approval (deliverable_id={target_deliv.deliverable.id if target_deliv else 'N/A'})")

    if target_deliv:
        deliv_id = target_deliv.deliverable.id
        # Find which run this deliverable belongs to
        source_run_id = target_deliv.versions[0].source_run_id if target_deliv.versions else None
        source_task_id = target_deliv.versions[0].source_task_id if target_deliv.versions else None
        print(f"  deliverable_id: {deliv_id}")
        print(f"  source_run_id: {source_run_id}")

        # Get the task and run for approval creation
        target_task = task_repo.get_by_id(source_task_id) if source_task_id else None
        target_run = run_repo.get_by_id(source_run_id) if source_run_id else base_run

        # Call approval auto-create via real function
        _auto_create_run_approval(
            worker=worker,
            deliverable_record=target_deliv,
            task=target_task or base_task,
            run=target_run or base_run,
        )
        worker_session.commit()

        # Verify approval was created
        deliverable_session2 = SessionLocal()
        try:
            ar2 = ApprovalRepository(deliverable_session2)
            created_approval = ar2.get_latest_record_by_deliverable_id(deliv_id)
            check(created_approval is not None, "approval record created")
            if created_approval:
                ap = created_approval.approval
                print(f"    approval.status: {ap.status.value}")
                print(f"    approval.deliverable_id: {ap.deliverable_id}")
                check(ap.status.value in ("pending_approval", "pending"), f"approval is pending (got {ap.status.value})")
                check(ap.deliverable_id == deliv_id, f"approval.deliverable_id matches ({ap.deliverable_id})")
                check(ap.project_id == project_id, f"approval.project_id matches ({ap.project_id})")
        finally:
            deliverable_session2.close()

        # 6b: idempotency — call again with same deliverable → should skip
        _auto_create_run_approval(
            worker=worker,
            deliverable_record=target_deliv,
            task=target_task or base_task,
            run=target_run or base_run,
        )
        worker_session.commit()

        deliverable_session3 = SessionLocal()
        try:
            ar3 = ApprovalRepository(deliverable_session3)
            # Count approvals for this deliverable — should still be 1
            all_approvals_for_deliv = ar3.list_records_by_project_id(project_id)
            matching = [a for a in all_approvals_for_deliv if a.approval.deliverable_id == deliv_id]
            check(len(matching) == 1, f"idempotent — only 1 approval for deliverable (got {len(matching)})")
        finally:
            deliverable_session3.close()

    deliverable_session.close()

    # -- Phase 7: API-level joint data closure check -----------------
    print()
    print("=" * 60)
    print("PHASE 7: API-level joint data closure")
    print("=" * 60)

    with TestClient(app) as client2:
        dr = client2.get(f"/deliverables/projects/{project_id}").json()
        total_deliv = dr.get("total_deliverables", 0)
        check(total_deliv >= 1, f"GET /deliverables returns data (total={total_deliv})")

        ar = client2.get(f"/approvals/projects/{project_id}").json()
        total_approval = ar.get("total_requests", 0)
        check(total_approval >= 1, f"GET /approvals returns data (total_requests={total_approval})")

        if dr.get("deliverables") and ar.get("approvals"):
            deliv_id_list = {d["id"] for d in dr["deliverables"]}
            approval_deliv_ids = {a.get("deliverable_id") for a in ar["approvals"] if a.get("deliverable_id")}
            overlap = deliv_id_list & approval_deliv_ids
            check(len(overlap) >= 1, f"deliverable <-> approval linkage exists (overlap={len(overlap)})")

    worker_session.close()

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
