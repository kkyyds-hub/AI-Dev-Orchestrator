"""BCL-08: V5 backend closure evidence rollup.

Read-only aggregation of all existing DB / file / config evidence into one
JSON evidence package.  Does NOT run provider calls, git writes, workers,
or re-run any BCL smoke.  Only consumes data that already exists on disk.

Output:  tmp/v5-backend-closure-rollup/v5_backend_closure_rollup.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = RUNTIME_ROOT / "tmp" / "v5-backend-closure-rollup"
OUTPUT_FILE = OUTPUT_DIR / "v5_backend_closure_rollup.json"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_runtime_data_dir() -> Path:
    """Resolve the effective RUNTIME_DATA_DIR."""
    env_val = os.environ.get("RUNTIME_DATA_DIR")
    if env_val:
        return Path(env_val).resolve()
    return (RUNTIME_ROOT / "data").resolve()


def _read_json_file(path: Path) -> dict | None:
    """Read a JSON file safely; return None on any error."""
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# -- Rollup builder ---------------------------------------------------------

def build_rollup() -> dict:
    evidence_sources: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    result: dict = {
        "generated_at": utc_now_iso(),
        "pass_ready": False,
        "blockers": blockers,
        "warnings": warnings,
        "provider": {},
        "project_diagnostics": {},
        "worker_runs": {},
        "team_control_budget": {},
        "repository_git_write": {},
        "cost_dashboard": {},
        "evidence_sources": evidence_sources,
    }

    runtime_data_dir = _read_runtime_data_dir()

    # --- DB access --------------------------------------------------------
    try:
        from app.core.db import init_database, SessionLocal
    except Exception as exc:
        blockers.append(f"db_import_failed: {exc}")
        return result

    try:
        init_database()
        evidence_sources.append("SQLite DB (via init_database)")
    except Exception as exc:
        blockers.append(f"db_init_failed: {exc}")
        return result

    session = SessionLocal()
    try:
        from app.repositories.project_repository import ProjectRepository
        from app.repositories.task_repository import TaskRepository
        from app.repositories.run_repository import RunRepository
        from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
        from app.repositories.repository_snapshot_repository import RepositorySnapshotRepository
        from app.repositories.change_batch_repository import ChangeBatchRepository
        from app.repositories.commit_candidate_repository import CommitCandidateRepository

        proj_repo = ProjectRepository(session)
        task_repo = TaskRepository(session)
        run_repo = RunRepository(session)
        ws_repo = RepositoryWorkspaceRepository(session)
        snap_repo = RepositorySnapshotRepository(session)
        cb_repo = ChangeBatchRepository(session)
        cc_repo = CommitCandidateRepository(session)

        projects = proj_repo.list_all()
        evidence_sources.append("ProjectRepository.list_all()")

        if not projects:
            blockers.append("no_project: no projects exist in the runtime DB")
            result["project_diagnostics"] = {"project_count": 0, "note": "No projects found."}
        else:
            result["project_diagnostics"]["project_count"] = len(projects)

        # --- Provider evidence -------------------------------------------
        provider_config_path = (
            runtime_data_dir / "provider-settings" / "openai-provider-config.json"
        )
        provider_config = _read_json_file(provider_config_path)
        provider_configured = False
        provider_base_url = None
        if provider_config:
            evidence_sources.append(str(provider_config_path.relative_to(RUNTIME_ROOT.parent)))
            api_key = provider_config.get("api_key") or ""
            provider_configured = bool(api_key and api_key.strip())
            provider_base_url = provider_config.get("base_url")

        # Check env for API key as fallback
        env_key = os.environ.get("OPENAI_API_KEY") or ""
        if not provider_configured and env_key and env_key.strip():
            provider_configured = True
            evidence_sources.append("env:OPENAI_API_KEY")

        result["provider"] = {
            "configured": provider_configured,
            "base_url": provider_base_url,
            "last_test_status": "unknown",
            "cache_telemetry_visible": False,
            "real_run_receipt_exists": False,
            "note": (
                "Provider config read from disk + env. "
                "No live connectivity test is run by this script."
            ),
        }

        # --- Per-project evidence ----------------------------------------
        total_tasks = 0
        total_runs = 0
        total_succeeded = 0
        total_failed_blocked = 0
        mode_counter: Counter = Counter()
        provider_cache_reported = 0
        provider_cache_not_reported = 0
        provider_cache_missing = 0
        provider_cache_read_tokens = 0
        any_budget_hard_stop = False
        any_budget_project_control = False
        any_workspace_bound = False
        any_snapshot = False
        any_git_write = False
        any_change_batch = False
        any_commit_candidate = False

        for project in projects:
            pid = project.id
            tasks = task_repo.list_by_project_id(pid)
            total_tasks += len(tasks)

            task_ids = [t.id for t in tasks]
            runs = run_repo.list_by_task_ids(task_ids) if task_ids else []
            total_runs += len(runs)

            for run in runs:
                if run.status and run.status.value == "succeeded":
                    total_succeeded += 1
                if run.status and run.status.value in ("failed", "blocked"):
                    total_failed_blocked += 1
                mode_counter[run.token_accounting_mode or "missing"] += 1

                cs = getattr(run, "cache_source", None)
                if cs == "provider_reported":
                    provider_cache_reported += 1
                    provider_cache_read_tokens += getattr(run, "cache_read_tokens", 0) or 0
                elif cs == "not_reported":
                    provider_cache_not_reported += 1
                else:
                    provider_cache_missing += 1

                # Check for real provider receipt
                if run.provider_receipt_id:
                    result["provider"]["real_run_receipt_exists"] = True
                if cs == "provider_reported":
                    result["provider"]["cache_telemetry_visible"] = True

            # Workspace
            ws = ws_repo.get_by_project_id(pid)
            if ws:
                any_workspace_bound = True
                snap = snap_repo.get_by_project_id(pid)
                if snap:
                    any_snapshot = True

                # Git write tracking
                cb_list = cb_repo.list_by_project_id(pid)
                if cb_list:
                    any_change_batch = True
                for cb in cb_list:
                    cc = cc_repo.get_by_change_batch_id(cb.id)
                    if cc:
                        any_commit_candidate = True
                    from app.services.git_write_state_tracker import has_git_write_actions_triggered
                    if has_git_write_actions_triggered(cb.id):
                        any_git_write = True
                        break

            # Budget policy
            try:
                from app.core.db_tables import ProjectTable
                row = session.get(ProjectTable, pid)
                if row and row.budget_policy_json and row.budget_policy_json != "{}":
                    bp = json.loads(row.budget_policy_json)
                    if isinstance(bp, dict) and bp:
                        if bp.get("hard_stop_enabled"):
                            any_budget_hard_stop = True
                        if bp.get("daily_budget_usd", 0) > 0 or bp.get("hard_stop_enabled"):
                            any_budget_project_control = True
            except Exception:
                pass

        evidence_sources.append("TaskRepository.list_by_project_id() × projects")
        evidence_sources.append("RunRepository.list_by_task_ids()")
        evidence_sources.append("RepositoryWorkspaceRepository / SnapshotRepository")
        evidence_sources.append("ChangeBatchRepository / CommitCandidateRepository")
        evidence_sources.append("git_write_state_tracker.has_git_write_actions_triggered()")

        # --- Worker / run evidence ---------------------------------------
        result["worker_runs"] = {
            "total_runs": total_runs,
            "total_tasks": total_tasks,
            "succeeded_runs": total_succeeded,
            "failed_or_blocked_runs": total_failed_blocked,
            "mode_breakdown": dict(mode_counter),
            "provider_reported_runs": mode_counter.get("provider_reported", 0),
            "heuristic_runs": mode_counter.get("heuristic", 0),
            "provider_mock_runs": mode_counter.get("provider_mock", 0),
            "missing_mode_runs": mode_counter.get("missing", 0),
            "legacy_missing_note": (
                "missing runs are legacy / replay / abnormal compatibility boundary. "
                "Normal worker main chain does NOT write missing mode."
            ),
            "fallback_contract": {
                "provider_reported_run_count": mode_counter.get("provider_reported", 0),
                "heuristic_run_count": mode_counter.get("heuristic", 0),
                "missing_mode_run_count": mode_counter.get("missing", 0),
                "fallback_active": (
                    mode_counter.get("heuristic", 0) > 0
                    or mode_counter.get("missing", 0) > 0
                ),
            },
            "provider_cache": {
                "reported_run_count": provider_cache_reported,
                "not_reported_run_count": provider_cache_not_reported,
                "missing_run_count": provider_cache_missing,
                "cache_read_tokens": provider_cache_read_tokens,
            },
        }

        # --- Team control / budget evidence ------------------------------
        result["team_control_budget"] = {
            "any_budget_policy_configured": any_budget_project_control,
            "any_hard_stop_enabled": any_budget_hard_stop,
            "budget_policy_source": (
                "project_team_control" if any_budget_hard_stop
                else "project_team_control_soft" if any_budget_project_control
                else "not_configured"
            ),
            "budget_guard_blocked_evidence": (
                "indirect: failed_or_blocked_runs may include budget-blocked runs"
                if total_failed_blocked > 0
                else "none"
            ),
            "note": (
                "Read from ProjectTable.budget_policy_json. "
                "No live BudgetGuard evaluation is run."
            ),
        }

        # --- Repository / git write evidence -----------------------------
        result["repository_git_write"] = {
            "any_workspace_bound": any_workspace_bound,
            "any_snapshot": any_snapshot,
            "any_change_batch": any_change_batch,
            "any_commit_candidate": any_commit_candidate,
            "any_git_write_triggered": any_git_write,
            "day15_flow_status": "unknown",
            "release_gate_status": "unknown",
            "note": (
                "Read from RepositoryWorkspace, RepositorySnapshot, "
                "ChangeBatch, CommitCandidate, and git_write_state_tracker. "
                "Full release gate evaluation is not run."
            ),
        }

        # --- Cost dashboard evidence -------------------------------------
        result["cost_dashboard"] = {
            "available": total_runs > 0,
            "provider_cache_available": provider_cache_reported > 0,
            "missing_source": "legacy_or_replay" if mode_counter.get("missing", 0) > 0 else "none",
        }

        # --- Determine pass_ready / blockers -----------------------------
        if not projects:
            blockers.append("no_project: create at least one project")
        if not provider_configured:
            blockers.append("provider_not_configured: configure OpenAI API key")
        if not any_workspace_bound:
            blockers.append("repository_not_bound: bind a repository workspace")
        elif not any_snapshot:
            blockers.append("snapshot_missing: refresh repository snapshot")
        if total_tasks == 0:
            blockers.append("no_tasks: create tasks via planning or manual")
        if mode_counter.get("missing", 0) > 0:
            warnings.append(
                f"{mode_counter['missing']} runs have missing token_accounting_mode "
                "(legacy/replay/abnormal)"
            )
        if not any_git_write and any_change_batch:
            warnings.append("git write not yet triggered despite change batches existing")

        # pass_ready: all critical evidence points are covered
        result["pass_ready"] = (
            len(projects) > 0
            and provider_configured
            and any_workspace_bound
            and any_snapshot
            and total_tasks > 0
            and mode_counter.get("provider_reported", 0) > 0
            and not blockers
        )

    finally:
        session.close()

    evidence_sources.append("runtime_data_dir: provider-settings, repository-release-gates, repository-git-writes")
    return result


# -- Main -------------------------------------------------------------------

def main() -> None:
    rollup = build_rollup()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(rollup, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Rollup written to: {OUTPUT_FILE}")
    print(f"pass_ready: {rollup.get('pass_ready')}")
    blockers = rollup.get("blockers", [])
    if blockers:
        print(f"blockers ({len(blockers)}):")
        for b in blockers:
            print(f"  - {b}")
    else:
        print("blockers: none")
    warnings = rollup.get("warnings", [])
    if warnings:
        print(f"warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    print(f"evidence_sources: {len(rollup.get('evidence_sources', []))} entries")


if __name__ == "__main__":
    main()
