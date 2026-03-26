"""V4-D Day16 smoke checks for V4 end-to-end acceptance and documentation closure."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day16-v4-e2e-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day16-v4-e2e"
SMOKE_REPORT_PATH = SMOKE_ROOT / "v4-day16-e2e-report.json"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _remove_readonly(func: Any, path: str, _: Any) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _run_git(*args: str) -> str:
    completed_process = subprocess.run(
        ["git", *args],
        cwd=SMOKE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: "
            f"{completed_process.stderr or completed_process.stdout}"
        )

    return (completed_process.stdout or "").strip()


def _write_file(relative_path: str, content: str) -> None:
    file_path = SMOKE_REPOSITORY_ROOT / Path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    _write_file(
        "apps/web/package.json",
        json.dumps(
            {
                "name": "day16-smoke-web",
                "private": True,
                "scripts": {"build": "echo build", "typecheck": "echo typecheck"},
                "devDependencies": {"typescript": "^5.8.2"},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        "\"\"\"Day16 smoke placeholder repositories route.\"\"\"\n\n"
        "ROUTES = [\"/repositories\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/projects.py",
        "\"\"\"Day16 smoke placeholder projects route.\"\"\"\n\n"
        "ROUTES = [\"/projects\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/approvals.py",
        "\"\"\"Day16 smoke placeholder approvals route.\"\"\"\n\n"
        "ROUTES = [\"/approvals\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/services/repository_release_gate_service.py",
        "\"\"\"Day16 smoke placeholder release-gate service.\"\"\"\n\n"
        "def summarize_release_gate() -> str:\n"
        "    return \"day16-release-gate\"\n",
    )
    _write_file(
        "apps/web/src/features/projects/ProjectOverviewPage.tsx",
        "export function ProjectOverviewPage() "
        "{ return <div>Day16 Project Overview</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/DiffSummaryPage.tsx",
        "export function DiffSummaryPage() "
        "{ return <div>Day16 Diff Summary</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/CommitDraftPanel.tsx",
        "export function CommitDraftPanel() "
        "{ return <div>Day16 Commit Draft</div>; }\n",
    )
    _write_file(
        "docs/day16-e2e-notes.md",
        "# Day16\n\nV4 end-to-end acceptance smoke notes.\n",
    )
    _write_file("README.md", "# Day16 Smoke Repo\n")
    _write_file(".gitignore", "node_modules/\n.tmp/\n")

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day16 smoke repo")

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ALLOWED_WORKSPACE_ROOT)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _request_json(
    client: Any,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> Any:
    response = client.request(method, path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, "
            f"got {response.status_code}: {response.text}"
        )

    return response.json()


def _create_project(client: Any) -> Any:
    return _request_json(
        client,
        "POST",
        "/projects",
        expected_status=201,
        json_body={
            "name": "Day16 V4 e2e acceptance project",
            "summary": "Run one minimum V4 Day01-Day15 acceptance chain for Day16 closure.",
        },
    )


def _bind_repository(client: Any, *, project_id: str) -> Any:
    return _request_json(
        client,
        "PUT",
        f"/repositories/projects/{project_id}",
        expected_status=200,
        json_body={
            "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
            "display_name": "day16-smoke-repo",
            "default_base_branch": "main",
        },
    )


def _create_task(
    client: Any,
    *,
    project_id: str,
    title: str,
    input_summary: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/tasks",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "title": title,
            "input_summary": input_summary,
            "acceptance_criteria": [
                "V4 minimum e2e chain can be accepted on Day16",
                "Day16 remains read-only for real git writes",
            ],
        },
    )


def _create_deliverable(
    client: Any,
    *,
    project_id: str,
    task_id: str,
    title: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/deliverables",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "type": "code_plan",
            "title": title,
            "stage": "planning",
            "created_by_role_code": "engineer",
            "summary": "Day16 smoke deliverable summary.",
            "content": "# Day16\n\nSmoke deliverable.",
            "content_format": "markdown",
            "source_task_id": task_id,
        },
    )


def _create_change_plan(
    client: Any,
    *,
    project_id: str,
    task_id: str,
    deliverable_id: str,
    title: str,
    source_summary: str,
    focus_terms: list[str],
    target_files: list[dict[str, Any]],
    verification_commands: list[str],
    verification_template_ids: list[str],
) -> Any:
    return _request_json(
        client,
        "POST",
        f"/planning/projects/{project_id}/change-plans",
        expected_status=201,
        json_body={
            "task_id": task_id,
            "title": title,
            "primary_deliverable_id": deliverable_id,
            "related_deliverable_ids": [deliverable_id],
            "intent_summary": f"{title} for Day16 e2e smoke.",
            "source_summary": source_summary,
            "focus_terms": focus_terms,
            "target_files": target_files,
            "expected_actions": [
                "connect Day01-Day14 repository capabilities",
                "produce Day15 read-only release judgement snapshots",
            ],
            "risk_notes": [
                "Day16 accepts review closure only; no real git commit/push/pr/merge.",
            ],
            "verification_commands": verification_commands,
            "verification_template_ids": verification_template_ids,
        },
    )


def _create_change_batch(
    client: Any,
    *,
    project_id: str,
    change_plan_ids: list[str],
) -> Any:
    return _request_json(
        client,
        "POST",
        f"/repositories/projects/{project_id}/change-batches",
        expected_status=200,
        json_body={
            "title": "Day16 V4 acceptance batch",
            "change_plan_ids": change_plan_ids,
        },
    )


def _record_verification_run(
    client: Any,
    *,
    project_id: str,
    change_plan_id: str,
    change_batch_id: str,
    verification_template_id: str,
    output_summary: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/runs/verification",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "change_plan_id": change_plan_id,
            "change_batch_id": change_batch_id,
            "verification_template_id": verification_template_id,
            "status": "passed",
            "duration_seconds": 7.8,
            "output_summary": output_summary,
        },
    )


def _apply_workspace_changes() -> None:
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        "\"\"\"Day16 smoke placeholder repositories route.\"\"\"\n\n"
        "ROUTES = [\n"
        "    \"/repositories\",\n"
        "    \"/repositories/projects/{project_id}/day15-flow\",\n"
        "    \"/repositories/projects/{project_id}/file-locator/search\",\n"
        "]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/projects.py",
        "\"\"\"Day16 smoke placeholder projects route.\"\"\"\n\n"
        "ROUTES = [\"/projects\", \"/projects/{project_id}/day15-repository-flow\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/approvals.py",
        "\"\"\"Day16 smoke placeholder approvals route.\"\"\"\n\n"
        "ROUTES = [\"/approvals\", \"/approvals/projects/{project_id}/day15-release-judgement\"]\n",
    )
    _write_file(
        "apps/web/src/features/projects/ProjectOverviewPage.tsx",
        "export function ProjectOverviewPage() "
        "{ return <div>Day16 Flow Overview</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/DiffSummaryPage.tsx",
        "export function DiffSummaryPage() "
        "{ return <div>Day16 Evidence Step</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/CommitDraftPanel.tsx",
        "export function CommitDraftPanel() "
        "{ return <div>Day16 Release Judgement</div>; }\n",
    )
    _write_file(
        "docs/day16-e2e-notes.md",
        "# Day16\n\nV4 end-to-end acceptance smoke notes.\n\n- Acceptance chain connected.\n",
    )


def _target_files_from_context_pack(context_pack: Any) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": entry["relative_path"],
            "language": entry["language"],
            "file_type": entry["file_type"],
            "rationale": f"Day16 e2e target file: {entry['relative_path']}",
            "match_reasons": entry["match_reasons"],
        }
        for entry in context_pack["entries"]
    ]


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])

        workspace = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            workspace["default_base_branch"] == "main",
            "Day16 smoke requires the repository to keep the main baseline branch.",
        )

        snapshot_refresh = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(
            snapshot_refresh["status"] == "success",
            "Day16 smoke requires snapshot refresh success.",
        )
        snapshot_latest = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/snapshot",
            expected_status=200,
        )
        _assert(
            snapshot_latest["file_count"] >= 8,
            "Day16 smoke expects the repository snapshot to include baseline files.",
        )

        clean_change_session = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/change-session",
            expected_status=200,
        )
        _assert(
            clean_change_session["workspace_status"] == "clean"
            and clean_change_session["guard_status"] == "ready",
            "Day16 smoke expects a clean/ready Day03 session before workspace changes.",
        )

        baseline = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
        )
        template_ids_by_category = {
            template["category"]: template["id"] for template in baseline["templates"]
        }
        _assert(
            {"build", "test", "lint", "typecheck"} == set(template_ids_by_category),
            "Day16 smoke requires Day09 baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="Connect Day16 backend acceptance chain",
            input_summary=(
                "Cover repository routes and release-gate checkpoints for Day16 closure."
            ),
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="Connect Day16 frontend acceptance panels",
            input_summary=(
                "Show Day16 closure status in project overview, diff summary and commit draft panel."
            ),
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day16 backend acceptance plan",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day16 frontend acceptance plan",
        )

        locator_backend = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "task_id": task_backend["id"],
                "path_prefixes": ["runtime/orchestrator/app/api/routes"],
                "module_names": ["routes"],
                "file_types": ["py"],
                "limit": 10,
            },
        )
        backend_candidate_paths = {
            candidate["relative_path"] for candidate in locator_backend["candidates"]
        }
        _assert(
            "runtime/orchestrator/app/api/routes/repositories.py"
            in backend_candidate_paths,
            "Day16 backend locator should include repositories route file.",
        )
        _assert(
            "runtime/orchestrator/app/api/routes/projects.py" in backend_candidate_paths,
            "Day16 backend locator should include projects route file.",
        )
        _assert(
            "runtime/orchestrator/app/api/routes/approvals.py"
            in backend_candidate_paths,
            "Day16 backend locator should include approvals route file.",
        )

        locator_frontend = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "task_id": task_frontend["id"],
                "path_prefixes": ["apps/web/src/features/repositories"],
                "module_names": ["repositories"],
                "file_types": ["tsx"],
                "limit": 10,
            },
        )
        frontend_candidate_paths = {
            candidate["relative_path"] for candidate in locator_frontend["candidates"]
        }
        _assert(
            "apps/web/src/features/repositories/DiffSummaryPage.tsx"
            in frontend_candidate_paths,
            "Day16 frontend locator should include diff summary page.",
        )
        _assert(
            "apps/web/src/features/repositories/CommitDraftPanel.tsx"
            in frontend_candidate_paths,
            "Day16 frontend locator should include commit draft panel.",
        )

        backend_selected_paths = sorted(backend_candidate_paths)[:3]
        frontend_selected_paths = sorted(frontend_candidate_paths)[:2]
        context_pack_backend = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/context-pack",
            expected_status=200,
            json_body={
                "task_id": task_backend["id"],
                "selected_paths": backend_selected_paths,
                "max_total_bytes": 5_000,
                "max_bytes_per_file": 2_500,
            },
        )
        _assert(
            context_pack_backend["included_file_count"] >= 2,
            "Day16 backend context pack should include at least two files.",
        )

        context_pack_frontend = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/context-pack",
            expected_status=200,
            json_body={
                "task_id": task_frontend["id"],
                "selected_paths": frontend_selected_paths,
                "max_total_bytes": 5_000,
                "max_bytes_per_file": 2_500,
            },
        )
        _assert(
            context_pack_frontend["included_file_count"] >= 1,
            "Day16 frontend context pack should include at least one file.",
        )

        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day16 backend acceptance plan",
            source_summary=context_pack_backend["source_summary"],
            focus_terms=context_pack_backend["focus_terms"],
            target_files=_target_files_from_context_pack(context_pack_backend),
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/api/routes/repositories.py",
                "python -m py_compile runtime/orchestrator/app/api/routes/projects.py",
                "python -m py_compile runtime/orchestrator/app/api/routes/approvals.py",
            ],
            verification_template_ids=[
                template_ids_by_category["build"],
                template_ids_by_category["lint"],
            ],
        )
        change_plan_frontend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            deliverable_id=deliverable_frontend["id"],
            title="Day16 frontend acceptance plan",
            source_summary=context_pack_frontend["source_summary"],
            focus_terms=context_pack_frontend["focus_terms"],
            target_files=_target_files_from_context_pack(context_pack_frontend),
            verification_commands=["cmd /c npm run build"],
            verification_template_ids=[
                template_ids_by_category["test"],
                template_ids_by_category["typecheck"],
            ],
        )

        change_batch = _create_change_batch(
            client,
            project_id=project["id"],
            change_plan_ids=[change_plan_backend["id"], change_plan_frontend["id"]],
        )
        _assert(
            change_batch["status"] == "preparing",
            "Day16 smoke expects new change batches to start in preparing status.",
        )

        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            output_summary="Day16 backend verification passed.",
        )
        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_frontend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["typecheck"],
            output_summary="Day16 frontend verification passed.",
        )

        preflight_ready = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/preflight",
            expected_status=200,
            json_body={},
        )
        preflight_status = preflight_ready["preflight"]["status"]
        if preflight_status == "blocked_requires_confirmation":
            preflight_ready = _request_json(
                client,
                "POST",
                f"/approvals/repository-preflight/{change_batch['id']}/actions",
                expected_status=200,
                json_body={
                    "action": "approve",
                    "actor_name": "boss",
                    "summary": "day16 acceptance confirms preflight findings",
                    "comment": "manual confirmation keeps Day16 read-only closure",
                    "highlighted_risks": [],
                },
            )
            preflight_status = preflight_ready["preflight"]["status"]
        _assert(
            preflight_status in {"ready_for_execution", "manual_confirmed"},
            "Day16 smoke requires a preflight-ready batch.",
        )

        _apply_workspace_changes()
        head_before = _run_git("rev-parse", "HEAD")

        blocked_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            blocked_gate["blocked"] is True and "commit_draft" in blocked_gate["missing_item_keys"],
            "Before commit draft generation, Day16 release gate should be blocked by commit_draft.",
        )

        approve_while_blocked = client.post(
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "boss",
                "summary": "try approve while blocked",
            },
        )
        _assert(
            approve_while_blocked.status_code == 409,
            "Approve action must be blocked while release checklist has gaps.",
        )

        evidence_package = _request_json(
            client,
            "GET",
            (
                f"/deliverables/projects/{project['id']}/change-evidence"
                f"?change_batch_id={change_batch['id']}"
            ),
            expected_status=200,
        )
        _assert(
            evidence_package["selected_change_batch_id"] == change_batch["id"],
            "Evidence package should bind to the selected Day16 change batch.",
        )
        _assert(
            evidence_package["diff_summary"]["metrics"]["changed_file_count"] >= 4,
            "Day16 evidence package should include changed files after workspace updates.",
        )

        commit_candidate = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
            json_body={},
        )
        _assert(
            commit_candidate["current_version_number"] == 1,
            "Day16 smoke requires Day13 commit-draft generation.",
        )
        time.sleep(0.02)

        commit_candidate_detail = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
        )
        _assert(
            commit_candidate_detail["current_version_number"] == 1,
            "Day16 commit-candidate detail should keep version 1 after first draft generation.",
        )
        project_commit_candidates = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/commit-candidates",
            expected_status=200,
        )
        _assert(
            any(item["change_batch_id"] == change_batch["id"] for item in project_commit_candidates),
            "Day16 project commit-candidate list should include the generated candidate.",
        )

        pending_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            pending_gate["blocked"] is False and pending_gate["status"] == "pending_approval",
            "After commit draft generation, Day16 release gate should become pending_approval.",
        )

        gate_after_approve = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "approve",
                "actor_name": "boss",
                "summary": "day16 e2e chain is review-ready",
                "comment": "approval establishes qualification only",
                "highlighted_risks": ["real git write still manual"],
                "requested_changes": [],
            },
        )
        _assert(
            gate_after_approve["status"] == "approved"
            and gate_after_approve["release_qualification_established"] is True
            and gate_after_approve["git_write_actions_triggered"] is False,
            "Day16 approval should not trigger real Git writes.",
        )

        repository_release_gates = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/release-gates",
            expected_status=200,
        )
        _assert(
            repository_release_gates["total_batches"] >= 1,
            "Day16 release-gate list should include at least one change batch.",
        )

        release_checklist = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}/release-checklist",
            expected_status=200,
        )
        _assert(
            release_checklist["status"] == "approved",
            "Day16 release checklist should end in approved status.",
        )

        repository_day15_flow = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/day15-flow",
            expected_status=200,
        )
        _assert(
            repository_day15_flow["overall_status"] == "ready_for_review",
            "Repository Day15 flow should become ready_for_review in Day16 acceptance.",
        )
        _assert(
            repository_day15_flow["release_status"] == "approved"
            and repository_day15_flow["release_qualification_established"] is True
            and repository_day15_flow["git_write_actions_triggered"] is False,
            "Repository Day15 flow should expose approved release status only.",
        )

        project_day15_flow = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}/day15-repository-flow",
            expected_status=200,
        )
        _assert(
            project_day15_flow["overall_status"] == "ready_for_review"
            and project_day15_flow["release_status"] == "approved",
            "Project Day15 overview should match repository-side release status.",
        )

        approvals_day15_judgement = _request_json(
            client,
            "GET",
            (
                f"/approvals/projects/{project['id']}/day15-release-judgement"
                f"?change_batch_id={change_batch['id']}"
            ),
            expected_status=200,
        )
        _assert(
            approvals_day15_judgement["selected_status"] == "approved"
            and approvals_day15_judgement["release_qualification_established"] is True
            and approvals_day15_judgement["git_write_actions_triggered"] is False,
            "Approvals Day15 endpoint should expose approved read-only judgement.",
        )

        head_after = _run_git("rev-parse", "HEAD")
        _assert(
            head_before == head_after,
            "Day16 acceptance must not create real Git commits.",
        )

    decision_file = (
        SMOKE_RUNTIME_DATA_DIR / "repository-release-gates" / f"{change_batch['id']}.json"
    )
    _assert(
        decision_file.exists(),
        "Day16 smoke should persist release-gate decisions.",
    )
    decision_payload = json.loads(decision_file.read_text(encoding="utf-8"))

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "snapshot_file_count": snapshot_latest["file_count"],
        "change_session_guard_status": clean_change_session["guard_status"],
        "preflight_status": preflight_status,
        "backend_locator_candidate_count": locator_backend["candidate_count"],
        "frontend_locator_candidate_count": locator_frontend["candidate_count"],
        "backend_context_pack_file_count": context_pack_backend["included_file_count"],
        "frontend_context_pack_file_count": context_pack_frontend["included_file_count"],
        "repository_day15_status": repository_day15_flow["overall_status"],
        "project_day15_status": project_day15_flow["overall_status"],
        "approvals_day15_selected_status": approvals_day15_judgement["selected_status"],
        "project_release_gate_total_batches": repository_release_gates["total_batches"],
        "release_checklist_status": release_checklist["status"],
        "evidence_package_key": evidence_package["package_key"],
        "evidence_changed_file_count": evidence_package["diff_summary"]["metrics"][
            "changed_file_count"
        ],
        "commit_candidate_version": commit_candidate["current_version_number"],
        "blocked_before": blocked_gate["blocked"],
        "approve_blocked_status_code": approve_while_blocked.status_code,
        "final_release_status": gate_after_approve["status"],
        "release_qualification_established": gate_after_approve[
            "release_qualification_established"
        ],
        "head_unchanged": head_before == head_after,
        "git_write_actions_triggered": gate_after_approve["git_write_actions_triggered"],
        "decision_file": str(decision_file),
        "persisted_decision_count": len(decision_payload.get("decisions", [])),
    }
    SMOKE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["report_path"] = str(SMOKE_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
