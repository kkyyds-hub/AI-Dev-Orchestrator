"""V4-D Day15 smoke checks for the minimum repository closed-loop demo."""

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
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day15-repository-flow-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day15-repository-flow"


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
                "name": "day15-smoke-web",
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
        "\"\"\"Day15 smoke placeholder repositories route.\"\"\"\n\n"
        "ROUTES = [\"/repositories\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/projects.py",
        "\"\"\"Day15 smoke placeholder projects route.\"\"\"\n\n"
        "ROUTES = [\"/projects\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/approvals.py",
        "\"\"\"Day15 smoke placeholder approvals route.\"\"\"\n\n"
        "ROUTES = [\"/approvals\"]\n",
    )
    _write_file(
        "apps/web/src/features/projects/ProjectOverviewPage.tsx",
        "export function ProjectOverviewPage() "
        "{ return <div>Day15 Project Overview</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/DiffSummaryPage.tsx",
        "export function DiffSummaryPage() "
        "{ return <div>Day15 Diff Summary</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/CommitDraftPanel.tsx",
        "export function CommitDraftPanel() "
        "{ return <div>Day15 Commit Draft</div>; }\n",
    )
    _write_file("README.md", "# Day15 Smoke Repo\n")
    _write_file(".gitignore", "node_modules/\n.tmp/\n")

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day15 smoke repo")

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
            "name": "Day15 repository flow demo project",
            "summary": "Verify the Day01-Day14 minimum closed-loop on Day15.",
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
            "display_name": "day15-smoke-repo",
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
                "Day15 loop is connected end-to-end",
                "demo stays read-only and does not write real Git history",
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
            "summary": "Day15 smoke deliverable summary.",
            "content": "# Day15\n\nSmoke deliverable.",
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
            "intent_summary": f"{title} for Day15 smoke.",
            "source_summary": "Day15 smoke source summary.",
            "focus_terms": ["day15", "repository", "closed-loop"],
            "target_files": target_files,
            "expected_actions": [
                "connect Day01-Day14 capabilities",
                "publish Day15 read-only flow snapshots",
            ],
            "risk_notes": [
                "Day15 only demonstrates reviewable loop; no real git commit/push/pr/merge.",
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
            "title": "Day15 repository loop batch",
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
            "duration_seconds": 7.1,
            "output_summary": output_summary,
        },
    )


def _apply_workspace_changes() -> None:
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        "\"\"\"Day15 smoke placeholder repositories route.\"\"\"\n\n"
        "ROUTES = [\"/repositories\", \"/repositories/projects/{project_id}/day15-flow\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/projects.py",
        "\"\"\"Day15 smoke placeholder projects route.\"\"\"\n\n"
        "ROUTES = [\"/projects\", \"/projects/{project_id}/day15-repository-flow\"]\n",
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/approvals.py",
        "\"\"\"Day15 smoke placeholder approvals route.\"\"\"\n\n"
        "ROUTES = [\"/approvals\", \"/approvals/projects/{project_id}/day15-release-judgement\"]\n",
    )
    _write_file(
        "apps/web/src/features/projects/ProjectOverviewPage.tsx",
        "export function ProjectOverviewPage() "
        "{ return <div>Day15 Flow Overview</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/DiffSummaryPage.tsx",
        "export function DiffSummaryPage() "
        "{ return <div>Day15 Evidence Step</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/CommitDraftPanel.tsx",
        "export function CommitDraftPanel() "
        "{ return <div>Day15 Release Judgement</div>; }\n",
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])

        snapshot = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(snapshot["status"] == "success", "Day15 smoke requires snapshot success.")

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
            "Day15 smoke requires Day09 baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="Connect Day15 backend loop endpoints",
            input_summary="Add Day15 read-only aggregation endpoints.",
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="Connect Day15 frontend loop panels",
            input_summary="Show Day15 loop states in overview, diff and commit draft panels.",
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day15 backend plan",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day15 frontend plan",
        )

        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day15 backend loop plan",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/repositories.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "Day15 repository flow endpoint",
                    "match_reasons": ["day15", "backend"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/projects.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "Day15 project overview endpoint",
                    "match_reasons": ["day15", "backend"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/approvals.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "Day15 release judgement endpoint",
                    "match_reasons": ["day15", "backend"],
                },
            ],
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
            title="Day15 frontend loop plan",
            target_files=[
                {
                    "relative_path": "apps/web/src/features/projects/ProjectOverviewPage.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "Day15 overview card",
                    "match_reasons": ["day15", "frontend"],
                },
                {
                    "relative_path": "apps/web/src/features/repositories/DiffSummaryPage.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "Day15 evidence step card",
                    "match_reasons": ["day15", "frontend"],
                },
                {
                    "relative_path": "apps/web/src/features/repositories/CommitDraftPanel.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "Day15 release judgement card",
                    "match_reasons": ["day15", "frontend"],
                },
            ],
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

        preflight_ready = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/preflight",
            expected_status=200,
            json_body={},
        )
        _assert(
            preflight_ready["preflight"]["status"] in {"ready_for_execution", "manual_confirmed"},
            "Day15 smoke requires a preflight-ready batch.",
        )

        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            output_summary="Day15 verification passed.",
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
            "Before commit draft generation, release gate should be blocked by commit_draft.",
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
            "Evidence package should bind to selected change batch.",
        )
        _assert(
            evidence_package["diff_summary"]["metrics"]["changed_file_count"] >= 3,
            "Evidence package should include changed files.",
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
            "Day15 smoke requires Day13 commit draft generation.",
        )
        time.sleep(0.02)

        pending_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            pending_gate["blocked"] is False and pending_gate["status"] == "pending_approval",
            "After commit draft generation, release gate should become pending_approval.",
        )

        gate_after_approve = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "approve",
                "actor_name": "boss",
                "summary": "day15 loop is review-ready",
                "comment": "approval establishes qualification only",
                "highlighted_risks": ["real git write still manual"],
                "requested_changes": [],
            },
        )
        _assert(
            gate_after_approve["status"] == "approved"
            and gate_after_approve["release_qualification_established"] is True
            and gate_after_approve["git_write_actions_triggered"] is False,
            "Day15 approval should not trigger real Git writes.",
        )

        repository_day15_flow = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/day15-flow",
            expected_status=200,
        )
        _assert(
            repository_day15_flow["overall_status"] == "ready_for_review",
            "Repository Day15 flow should become ready_for_review.",
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
            "Day15 demo must not create real Git commits.",
        )

    decision_file = (
        SMOKE_RUNTIME_DATA_DIR / "repository-release-gates" / f"{change_batch['id']}.json"
    )
    _assert(
        decision_file.exists(),
        "Day15 smoke should persist release-gate decisions.",
    )
    decision_payload = json.loads(decision_file.read_text(encoding="utf-8"))

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "repository_day15_status": repository_day15_flow["overall_status"],
        "project_day15_status": project_day15_flow["overall_status"],
        "approvals_day15_selected_status": approvals_day15_judgement["selected_status"],
        "evidence_package_key": evidence_package["package_key"],
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
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
