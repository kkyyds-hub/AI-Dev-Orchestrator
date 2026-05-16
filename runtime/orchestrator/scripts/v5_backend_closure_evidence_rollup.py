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
    env_val = os.environ.get("RUNTIME_DATA_DIR")
    if env_val:
        return Path(env_val).resolve()
    return (RUNTIME_ROOT / "data").resolve()


def _read_json_file(path: Path) -> dict | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_json_file_list(path: Path) -> list[dict]:
    """Read a directory of {uuid}.json files; return list of parsed dicts."""
    try:
        if not path.exists() or not path.is_dir():
            return []
        results: list[dict] = []
        for f in sorted(path.iterdir()):
            if f.suffix == ".json":
                data = _read_json_file(f)
                if isinstance(data, dict):
                    data["_source_file"] = str(f.name)
                    results.append(data)
        return results
    except Exception:
        return []


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
        return _safety_check(result)

    try:
        init_database()
        evidence_sources.append("SQLite DB (via init_database)")
    except Exception as exc:
        blockers.append(f"db_init_failed: {exc}")
        return _safety_check(result)

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

        # --- Provider evidence -------------------------------------------
        provider_config_path = (
            runtime_data_dir / "provider-settings" / "openai-provider-config.json"
        )
        provider_config = _read_json_file(provider_config_path)
        provider_configured = False
        provider_base_url = None
        if provider_config:
            api_key = provider_config.get("api_key") or ""
            provider_configured = bool(api_key and api_key.strip())
            provider_base_url = provider_config.get("base_url")

        env_key = os.environ.get("OPENAI_API_KEY") or ""
        if not provider_configured and env_key and env_key.strip():
            provider_configured = True
            evidence_sources.append("env:OPENAI_API_KEY")
        if provider_config:
            evidence_sources.append("file:provider-settings/openai-provider-config.json")

        # --- Per-project aggregation -------------------------------------
        total_tasks = 0
        total_runs = 0
        total_succeeded = 0
        total_failed_blocked = 0
        mode_counter: Counter = Counter()
        provider_cache_reported = 0
        provider_cache_not_reported = 0
        provider_cache_missing = 0
        provider_cache_read_tokens = 0
        any_provider_receipt = False
        any_budget_hard_stop = False
        any_budget_project_control = False
        any_workspace_bound = False
        any_snapshot = False
        any_git_write = False
        any_change_batch = False
        any_commit_candidate = False

        diag_projects: list[dict] = []
        release_gate_summaries: list[dict] = []
        git_write_evidence: dict = {}
        latest_commit_sha_value: str | None = None
        evidence_files_read: list[str] = []

        # Read release gate decision files
        gate_dir = runtime_data_dir / "repository-release-gates"
        gate_files = _read_json_file_list(gate_dir)
        if gate_files:
            evidence_sources.append("file:repository-release-gates/*.json")
            evidence_files_read.append(str(gate_dir.relative_to(runtime_data_dir)))
        release_gate_status = "unknown"
        if gate_files:
            any_approved = any(
                any(d.get("action") == "approve" for d in g.get("decisions", []))
                for g in gate_files
            )
            release_gate_status = "approved" if any_approved else "pending_or_rejected"
        if not gate_files:
            release_gate_status = "unknown"

        # Read git write state files
        git_write_dir = runtime_data_dir / "repository-git-writes"
        git_write_files = _read_json_file_list(git_write_dir)
        if git_write_files:
            evidence_sources.append("file:repository-git-writes/*.json")
            evidence_files_read.append(str(git_write_dir.relative_to(runtime_data_dir)))
        for gw in git_write_files:
            if gw.get("git_write_actions_triggered"):
                any_git_write = True
            git_commit_data = gw.get("git_commit", {})
            if isinstance(git_commit_data, dict):
                sha = git_commit_data.get("commit_sha")
                if sha and sha != "unknown":
                    latest_commit_sha_value = str(sha)
            evidence_files_read.append(str(gw.get("_source_file", "")))

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

                if run.provider_receipt_id:
                    any_provider_receipt = True
                    result["provider"]["real_run_receipt_exists"] = True
                if cs == "provider_reported":
                    result["provider"]["cache_telemetry_visible"] = True

            # Project diagnostics via BCL-02 service
            diag_entry = _build_project_diag(session, pid)
            diag_projects.append(diag_entry)

            # Workspace
            ws = ws_repo.get_by_project_id(pid)
            if ws:
                any_workspace_bound = True
                snap = snap_repo.get_by_project_id(pid)
                if snap:
                    any_snapshot = True

                cb_list = cb_repo.list_by_project_id(pid)
                if cb_list:
                    any_change_batch = True
                for cb in cb_list:
                    cc = cc_repo.get_by_change_batch_id(cb.id)
                    if cc:
                        any_commit_candidate = True

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
        evidence_sources.append("git_write_state_tracker")

        # --- Project diagnostics output ----------------------------------
        result["project_diagnostics"] = {
            "project_count": len(projects),
            "projects": diag_projects,
        }

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
            "note": "Read from ProjectTable.budget_policy_json. No live BudgetGuard evaluation.",
        }

        # --- Repository / git write evidence -----------------------------
        result["repository_git_write"] = {
            "any_workspace_bound": any_workspace_bound,
            "any_snapshot": any_snapshot,
            "any_change_batch": any_change_batch,
            "any_commit_candidate": any_commit_candidate,
            "any_git_write_triggered": any_git_write,
            "release_gate_status": release_gate_status,
            "git_write_actions_triggered": any_git_write,
            "latest_commit_sha": latest_commit_sha_value,
            "evidence_files_read": evidence_files_read,
            "note": "Read from release-gate files, git-write files, DB repos.",
        }

        # --- Cost dashboard evidence -------------------------------------
        result["cost_dashboard"] = {
            "available": total_runs > 0,
            "provider_cache_available": provider_cache_reported > 0,
            "missing_source": (
                "legacy_or_replay" if mode_counter.get("missing", 0) > 0 else "none"
            ),
        }

        # --- Blockers ----------------------------------------------------
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
        if total_runs == 0:
            blockers.append("no_runs: no runs have been executed")
        else:
            if total_succeeded == 0:
                blockers.append("no_successful_run: no runs have succeeded")
            if mode_counter.get("provider_reported", 0) == 0:
                blockers.append(
                    "no_provider_reported_run: no runs with provider_reported token accounting"
                )
        if not any_provider_receipt and total_runs > 0:
            blockers.append(
                "missing_provider_receipt: no run has a provider_receipt_id"
            )
        if projects:
            if any(d.get("overall_status") == "blocked" for d in diag_projects):
                blockers.append(
                    "project_diagnostics_blocked: at least one project closure diagnostics shows blocked"
                )
            if any(
                d.get("overall_status") == "unknown"
                or "diagnostics_unavailable" in d.get("blocking_reason_codes", [])
                or "project_not_found" in d.get("blocking_reason_codes", [])
                for d in diag_projects
            ):
                blockers.append(
                    "diagnostics_unavailable: project closure diagnostics could not be evaluated"
                )

        # --- Gate blockers ------------------------------------------------
        if release_gate_status == "unknown":
            blockers.append(
                "release_gate_unknown: no approved release gate evidence found"
            )
        elif release_gate_status == "pending_or_rejected":
            blockers.append(
                "release_gate_not_approved: release gate is not approved"
            )

        # Warnings
        if mode_counter.get("missing", 0) > 0:
            warnings.append(
                f"{mode_counter['missing']} runs have missing token_accounting_mode "
                "(legacy/replay/abnormal)"
            )
        if not any_git_write and any_change_batch:
            warnings.append(
                "git write not yet triggered despite change batches existing"
            )
        if release_gate_status == "unknown" and any_change_batch:
            warnings.append(
                "release_gate_unknown: no release gate decision files found, "
                "but change batches exist"
            )
        if any(cb_diag.get("overall_status") == "unknown" for cb_diag in diag_projects):
            warnings.append(
                "diagnostics_unavailable: project closure diagnostics could "
                "not be evaluated for some projects"
            )

        # --- pass_ready --------------------------------------------------
        result["pass_ready"] = (
            len(projects) > 0
            and provider_configured
            and any_workspace_bound
            and any_snapshot
            and total_tasks > 0
            and total_runs > 0
            and total_succeeded > 0
            and mode_counter.get("provider_reported", 0) > 0
            and any_provider_receipt
            and not any(
                d.get("overall_status") in ("blocked", "unknown")
                for d in diag_projects
            )
            and not any(
                "diagnostics_unavailable" in d.get("blocking_reason_codes", [])
                or "project_not_found" in d.get("blocking_reason_codes", [])
                for d in diag_projects
            )
            and release_gate_status == "approved"
            and not blockers
        )

    finally:
        session.close()

    evidence_sources.append(
        "runtime_data_dir: provider-settings, repository-release-gates, "
        "repository-git-writes"
    )
    return _safety_check(result)


def _build_project_diag(session, project_id: UUID) -> dict:
    """Build one project diagnostics entry via BCL-02 service."""
    try:
        from app.services.project_closure_diagnostics_service import (
            build_project_closure_diagnostics,
            ProjectClosureDiagnosticsProjectNotFoundError,
        )
        from app.repositories.project_repository import ProjectRepository
        from app.repositories.task_repository import TaskRepository
        from app.repositories.run_repository import RunRepository
        from app.repositories.repository_workspace_repository import (
            RepositoryWorkspaceRepository,
        )
        from app.repositories.repository_snapshot_repository import (
            RepositorySnapshotRepository,
        )
        from app.repositories.agent_session_repository import AgentSessionRepository
        from app.repositories.approval_repository import ApprovalRepository
        from app.repositories.change_batch_repository import ChangeBatchRepository
        from app.repositories.commit_candidate_repository import CommitCandidateRepository
        from app.services.provider_config_service import ProviderConfigService
        from app.services.project_memory_service import ProjectMemoryService
        from app.repositories.deliverable_repository import DeliverableRepository
        from app.services.failure_review_service import FailureReviewService
        from app.repositories.failure_review_repository import FailureReviewRepository
        from app.services.run_logging_service import RunLoggingService

        result = build_project_closure_diagnostics(
            project_id=project_id,
            project_repository=ProjectRepository(session),
            task_repository=TaskRepository(session),
            run_repository=RunRepository(session),
            workspace_repository=RepositoryWorkspaceRepository(session),
            snapshot_repository=RepositorySnapshotRepository(session),
            agent_session_repository=AgentSessionRepository(session),
            approval_repository=ApprovalRepository(session),
            change_batch_repository=ChangeBatchRepository(session),
            commit_candidate_repository=CommitCandidateRepository(session),
            provider_config_service=ProviderConfigService(),
            project_memory_service=ProjectMemoryService(
                task_repository=TaskRepository(session),
                run_repository=RunRepository(session),
                approval_repository=ApprovalRepository(session),
                deliverable_repository=DeliverableRepository(session),
                project_repository=ProjectRepository(session),
                failure_review_service=FailureReviewService(
                    failure_review_repository=FailureReviewRepository(),
                    run_logging_service=RunLoggingService(),
                ),
            ),
        )
        return {
            "project_id": str(result.project_id),
            "overall_status": result.overall_status,
            "blocking_reason_codes": result.blocking_reason_codes,
            "next_actions": [
                {"code": a.code, "label": a.label, "api": a.api}
                for a in result.next_actions
            ],
        }
    except ProjectClosureDiagnosticsProjectNotFoundError:
        return {
            "project_id": str(project_id),
            "overall_status": "unknown",
            "blocking_reason_codes": ["project_not_found"],
            "next_actions": [],
        }
    except Exception as exc:
        return {
            "project_id": str(project_id),
            "overall_status": "unknown",
            "blocking_reason_codes": ["diagnostics_unavailable"],
            "next_actions": [],
            "error": str(exc),
        }


def _safety_check(result: dict) -> dict:
    """Ensure pass_ready=false always has at least one blocker."""
    if not result["pass_ready"] and not result["blockers"]:
        result["blockers"].append(
            "unknown_blocker: pass_ready is false but no explicit blocker "
            "was identified"
        )
    return result


# -- Main -------------------------------------------------------------------

def main() -> dict:
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
    return rollup


if __name__ == "__main__":
    main()
