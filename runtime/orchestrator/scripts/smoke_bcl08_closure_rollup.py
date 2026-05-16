"""BCL-08 smoke: verify the closure evidence rollup script.

Covers:
1. Empty runtime DB → no crash, pass_ready=false, blockers present.
2. JSON contains all required top-level keys.
3. No provider call, no git write triggered.
4. With seed data: aggregation works (mode breakcount, fallback, provider_cache).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import UUID

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl08-rollup-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _prepare_env() -> Path:
    """Set up a clean runtime data dir for smoke testing."""
    import shutil
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(str(SMOKE_RUNTIME_DATA_DIR), ignore_errors=True)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "50.00"
    os.environ["SESSION_BUDGET_USD"] = "80.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    (SMOKE_RUNTIME_DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
    return SMOKE_RUNTIME_DATA_DIR


def test_empty_db_no_crash() -> None:
    """Empty runtime DB must not crash; must return pass_ready=false with blockers."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    assert rollup["pass_ready"] is False, (
        f"Expected pass_ready=False for empty DB, got {rollup['pass_ready']}"
    )
    assert len(rollup["blockers"]) > 0, "Expected at least one blocker for empty DB"
    assert "no_project" in " ".join(rollup["blockers"]), (
        f"Expected no_project in blockers: {rollup['blockers']}"
    )
    print("PASS test_empty_db_no_crash")


def test_required_keys_present() -> None:
    """JSON output must contain all required top-level keys."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    required = {
        "generated_at", "pass_ready", "blockers", "warnings",
        "provider", "project_diagnostics", "worker_runs",
        "team_control_budget", "repository_git_write",
        "cost_dashboard", "evidence_sources",
    }
    missing = required - set(rollup.keys())
    assert not missing, f"Missing top-level keys: {missing}"
    print("PASS test_required_keys_present")


def test_no_provider_call_no_git_write() -> None:
    """Rollup must NOT call provider or perform git write."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup

    # Monkeypatch to detect any subprocess git calls
    import subprocess
    original_run = subprocess.run
    git_called = False

    def _detect_git(*args, **kwargs):
        nonlocal git_called
        cmd = args[0] if args else kwargs.get("args", [])
        cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
        if "git" in cmd_str.lower() and "commit" in cmd_str.lower():
            git_called = True
        return original_run(*args, **kwargs)

    subprocess.run = _detect_git
    try:
        rollup = build_rollup()
    finally:
        subprocess.run = original_run

    assert git_called is False, "Rollup must NOT trigger git write"
    # Provider note confirms no live test
    assert "No live connectivity test" in rollup["provider"].get("note", ""), (
        "Provider note must state no live test"
    )
    print("PASS test_no_provider_call_no_git_write")


def test_seed_data_aggregation() -> None:
    """With seed data, rollup aggregates run modes, fallback, provider_cache."""
    from app.core.db import SessionLocal, init_database
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus
    from uuid import uuid4

    init_database()

    session = SessionLocal()
    try:
        # Create project
        from app.domain.project import Project, ProjectStatus, ProjectStage
        proj = ProjectRepository(session).create(Project(
            id=uuid4(), name="BCL-08 Smoke", summary="Rollup test.",
            status=ProjectStatus.ACTIVE, stage=ProjectStage.INTAKE,
        ))

        # Create tasks
        task_repo = TaskRepository(session)
        from app.domain.task import Task
        t1 = task_repo.create(Task(id=uuid4(), project_id=proj.id,
                                    title="T1", input_summary="Task 1"))
        t2 = task_repo.create(Task(id=uuid4(), project_id=proj.id,
                                    title="T2", input_summary="Task 2"))
        t3 = task_repo.create(Task(id=uuid4(), project_id=proj.id,
                                    title="T3", input_summary="Task 3"))

        run_repo = RunRepository(session)
        # Run 1: provider_reported with cache
        r1 = run_repo.create_running_run(task_id=t1.id, model_name="test")
        run_repo.finish_run(run_id=r1.id, status=RunStatus.SUCCEEDED,
                            result_summary="ok", estimated_cost=0.01,
                            token_accounting_mode="provider_reported",
                            cache_source="provider_reported",
                            cache_read_tokens=10, cache_hit=True)

        # Run 2: heuristic
        r2 = run_repo.create_running_run(task_id=t2.id, model_name="test")
        run_repo.finish_run(run_id=r2.id, status=RunStatus.SUCCEEDED,
                            result_summary="ok", estimated_cost=0.01,
                            token_accounting_mode="heuristic",
                            cache_source="not_reported")

        # Run 3: missing (NULL token_accounting_mode)
        r3 = run_repo.create_running_run(task_id=t3.id, model_name="test")
        run_repo.finish_run(run_id=r3.id, status=RunStatus.SUCCEEDED,
                            result_summary="old", estimated_cost=0.01)
        session.commit()
    finally:
        session.close()

    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    wr = rollup["worker_runs"]
    assert wr["total_runs"] == 3
    assert wr["total_tasks"] == 3
    assert wr["provider_reported_runs"] == 1
    assert wr["heuristic_runs"] == 1
    assert wr["missing_mode_runs"] == 1
    assert wr["fallback_contract"]["missing_mode_run_count"] == 1
    assert wr["fallback_contract"]["fallback_active"] is True
    assert wr["provider_cache"]["reported_run_count"] == 1
    assert wr["provider_cache"]["not_reported_run_count"] == 1
    assert wr["provider_cache"]["missing_run_count"] == 1
    assert wr["provider_cache"]["cache_read_tokens"] == 10

    # provider evidence
    assert rollup["provider"]["real_run_receipt_exists"] is False  # no receipt_id set
    assert rollup["provider"]["cache_telemetry_visible"] is True

    # cost dashboard
    assert rollup["cost_dashboard"]["available"] is True
    assert rollup["cost_dashboard"]["missing_source"] == "legacy_or_replay"

    # evidence_sources have content
    assert len(rollup["evidence_sources"]) > 5

    print("PASS test_seed_data_aggregation")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    all_passed = True
    for fn in [
        test_empty_db_no_crash,
        test_required_keys_present,
        test_no_provider_call_no_git_write,
        test_seed_data_aggregation,
    ]:
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-08 smoke: ALL PASSED")
    else:
        print("BCL-08 smoke: SOME FAILED")
        sys.exit(1)
