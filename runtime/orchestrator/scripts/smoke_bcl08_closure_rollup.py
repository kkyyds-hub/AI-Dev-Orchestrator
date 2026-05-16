"""BCL-08 rework smoke: closure evidence rollup script.

Covers:
1. Empty DB → no crash, pass_ready=false, blockers contains no_project.
2. Required top-level keys present.
3. No provider call, no git write.
4. Has tasks but no provider_reported run → blockers includes no_provider_reported_run.
5. Seed data aggregation (mode breakdown, fallback, provider_cache).
6. repository_git_write outputs release_gate_status, git_write_actions_triggered, latest_commit_sha.
7. main() writes JSON file to disk.
8. pass_ready=false → blockers non-empty.
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


def _set_output_dir() -> None:
    """Override rollup output dir to smoke-specific location."""
    from scripts import v5_backend_closure_evidence_rollup as rollup_mod
    rollup_mod.OUTPUT_DIR = SMOKE_RUNTIME_DATA_DIR / "rollup-output"
    rollup_mod.OUTPUT_FILE = rollup_mod.OUTPUT_DIR / "v5_backend_closure_rollup.json"


def _reset_db_tables() -> None:
    """Delete all rows from all tables (clean reset without deleting DB file)."""
    from app.core.db import SessionLocal, init_database
    from app.core.db_tables import ORMBase
    init_database()
    session = SessionLocal()
    try:
        for table in reversed(ORMBase.metadata.sorted_tables):
            try:
                session.execute(table.delete())
            except Exception:
                pass
        session.commit()
    finally:
        session.close()


# -- Tests ---------------------------------------------------------------

def test_empty_db_no_crash() -> None:
    """Empty runtime DB → no crash, pass_ready=false, blockers has no_project."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    assert rollup["pass_ready"] is False
    assert len(rollup["blockers"]) > 0, "Must have blockers"
    assert any("no_project" in b for b in rollup["blockers"]), (
        f"Expected no_project in blockers: {rollup['blockers']}"
    )
    # Safety check: pass_ready=false + blockers empty should be impossible
    if not rollup["pass_ready"] and not rollup["blockers"]:
        raise AssertionError("pass_ready=false but blockers is empty!")
    print("PASS test_empty_db_no_crash")


def test_required_keys_present() -> None:
    """JSON must contain all required top-level keys."""
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

    # project_diagnostics must have project_count (not just empty)
    pd = rollup["project_diagnostics"]
    assert "project_count" in pd, f"project_diagnostics missing project_count: {pd}"

    # repository_git_write must have release_gate_status, git_write_actions_triggered, latest_commit_sha
    rgw = rollup["repository_git_write"]
    for key in ("release_gate_status", "git_write_actions_triggered", "latest_commit_sha"):
        assert key in rgw, f"repository_git_write missing {key}"

    print("PASS test_required_keys_present")


def test_no_provider_call_no_git_write() -> None:
    """Rollup must NOT call provider or perform git write."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup

    import subprocess
    original_run = subprocess.run
    git_called = False

    def _detect(*args, **kwargs):
        nonlocal git_called
        cmd = args[0] if args else kwargs.get("args", [])
        cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
        if "git" in cmd_str.lower() and "commit" in cmd_str.lower():
            git_called = True
        return original_run(*args, **kwargs)

    subprocess.run = _detect
    try:
        rollup = build_rollup()
    finally:
        subprocess.run = original_run

    assert git_called is False, "Must NOT trigger git write"
    assert "No live connectivity test" in rollup["provider"].get("note", "")
    print("PASS test_no_provider_call_no_git_write")


def test_no_provider_reported_run_blocked() -> None:
    """Has tasks+runs but no provider_reported → blocker includes no_provider_reported_run."""
    _reset_db_tables()
    from app.core.db import SessionLocal
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus
    from app.domain.project import Project, ProjectStatus, ProjectStage
    from app.domain.task import Task
    from uuid import uuid4

    session = SessionLocal()
    try:
        proj = ProjectRepository(session).create(Project(
            id=uuid4(), name="BCL-08 NoPR", summary="No provider_reported.",
            status=ProjectStatus.ACTIVE, stage=ProjectStage.INTAKE,
        ))
        t1 = TaskRepository(session).create(Task(
            id=uuid4(), project_id=proj.id, title="T1", input_summary="Task 1",
        ))
        r1 = RunRepository(session).create_running_run(task_id=t1.id, model_name="test")
        RunRepository(session).finish_run(
            run_id=r1.id, status=RunStatus.SUCCEEDED,
            result_summary="Heuristic only.", estimated_cost=0.01,
            token_accounting_mode="heuristic",
        )
        session.commit()
    finally:
        session.close()

    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    assert rollup["pass_ready"] is False
    blockers = rollup["blockers"]
    assert any("no_provider_reported_run" in b for b in blockers), (
        f"Expected no_provider_reported_run in blockers: {blockers}"
    )
    print("PASS test_no_provider_reported_run_blocked")


def test_seed_data_aggregation() -> None:
    """Seed data: mode breakdown, fallback, provider_cache all correct."""
    _reset_db_tables()
    from app.core.db import SessionLocal
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository
    from app.repositories.run_repository import RunRepository
    from app.domain.run import RunStatus
    from app.domain.project import Project, ProjectStatus, ProjectStage
    from app.domain.task import Task
    from uuid import uuid4

    session = SessionLocal()
    try:
        proj = ProjectRepository(session).create(Project(
            id=uuid4(), name="BCL-08 Agg", summary="Aggregation test.",
            status=ProjectStatus.ACTIVE, stage=ProjectStage.INTAKE,
        ))
        t1 = TaskRepository(session).create(Task(
            id=uuid4(), project_id=proj.id, title="T1", input_summary="1",
        ))
        t2 = TaskRepository(session).create(Task(
            id=uuid4(), project_id=proj.id, title="T2", input_summary="2",
        ))
        t3 = TaskRepository(session).create(Task(
            id=uuid4(), project_id=proj.id, title="T3", input_summary="3",
        ))

        repo = RunRepository(session)
        r1 = repo.create_running_run(task_id=t1.id, model_name="a")
        repo.finish_run(run_id=r1.id, status=RunStatus.SUCCEEDED,
                        result_summary="ok", estimated_cost=0.01,
                        token_accounting_mode="provider_reported",
                        cache_source="provider_reported",
                        cache_read_tokens=10, cache_hit=True)
        r2 = repo.create_running_run(task_id=t2.id, model_name="b")
        repo.finish_run(run_id=r2.id, status=RunStatus.SUCCEEDED,
                        result_summary="ok", estimated_cost=0.01,
                        token_accounting_mode="heuristic",
                        cache_source="not_reported")
        r3 = repo.create_running_run(task_id=t3.id, model_name="c")
        repo.finish_run(run_id=r3.id, status=RunStatus.SUCCEEDED,
                        result_summary="old", estimated_cost=0.01)
        session.commit()
    finally:
        session.close()

    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    wr = rollup["worker_runs"]
    assert wr["total_runs"] == 3
    assert wr["provider_reported_runs"] == 1
    assert wr["heuristic_runs"] == 1
    assert wr["missing_mode_runs"] == 1
    assert wr["fallback_contract"]["missing_mode_run_count"] == 1
    assert wr["fallback_contract"]["fallback_active"] is True
    assert wr["provider_cache"]["reported_run_count"] == 1
    assert wr["provider_cache"]["not_reported_run_count"] == 1
    assert wr["provider_cache"]["missing_run_count"] == 1
    assert wr["provider_cache"]["cache_read_tokens"] == 10

    # cost dashboard
    assert rollup["cost_dashboard"]["available"] is True
    assert rollup["cost_dashboard"]["missing_source"] == "legacy_or_replay"

    print("PASS test_seed_data_aggregation")


def test_repository_git_write_fields() -> None:
    """repository_git_write section has all required fields."""
    from scripts.v5_backend_closure_evidence_rollup import build_rollup
    rollup = build_rollup()

    rgw = rollup["repository_git_write"]
    required = {
        "any_workspace_bound", "any_snapshot", "any_change_batch",
        "any_commit_candidate", "any_git_write_triggered",
        "release_gate_status", "git_write_actions_triggered",
        "latest_commit_sha", "evidence_files_read",
    }
    missing = required - set(rgw.keys())
    assert not missing, f"repository_git_write missing fields: {missing}"

    # release_gate_status must be one of the known values
    assert rgw["release_gate_status"] in (
        "approved", "pending_or_rejected", "unknown"
    ), f"Unexpected release_gate_status: {rgw['release_gate_status']}"

    # latest_commit_sha should be None or a string
    assert rgw["latest_commit_sha"] is None or isinstance(rgw["latest_commit_sha"], str)

    # evidence_files_read must be a list
    assert isinstance(rgw["evidence_files_read"], list)

    print("PASS test_repository_git_write_fields")


def test_main_writes_json_file() -> None:
    """main() must write a real JSON file to disk."""
    from scripts.v5_backend_closure_evidence_rollup import main, OUTPUT_FILE

    rollup = main()

    assert OUTPUT_FILE.exists(), f"Output file not created: {OUTPUT_FILE}"
    # Re-read and validate
    data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    assert data["generated_at"] == rollup["generated_at"]
    assert "pass_ready" in data
    assert "blockers" in data

    # If pass_ready=false, blockers must be non-empty
    if not data["pass_ready"]:
        assert len(data["blockers"]) > 0, (
            "pass_ready=false but blockers is empty!"
        )

    print("PASS test_main_writes_json_file")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()
    _set_output_dir()

    from app.core.db import init_database

    all_passed = True
    # Order matters: tests that seed data must come after empty-db tests
    # because each test inits its own DB through the smoke harness
    for fn in [
        test_empty_db_no_crash,
        test_required_keys_present,
        test_no_provider_call_no_git_write,
        test_repository_git_write_fields,
        test_main_writes_json_file,
        test_no_provider_reported_run_blocked,
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
        print("BCL-08 smoke (rework): ALL PASSED")
    else:
        print("BCL-08 smoke (rework): SOME FAILED")
        sys.exit(1)
