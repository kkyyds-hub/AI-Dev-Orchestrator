"""V4-B Day08 smoke checks for execution-preflight risk guard and manual confirmation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day08-preflight-guard-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day08-preflight-guard"


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
            f"git {' '.join(args)} failed: {completed_process.stderr or completed_process.stdout}"
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
        "runtime/orchestrator/app/core/db.py",
        '"""Day08 smoke core db file."""\n\nDB_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/services/change_batch_service.py",
        '"""Day08 smoke service file."""\n\nclass ChangeBatchService:\n    pass\n',
    )
    _write_file(
        "runtime/orchestrator/app/services/preflight_note.py",
        '"""Day08 smoke preflight note file."""\n\nNOTE = "day08"\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        '"""Day08 smoke route file."""\n\nROUTES = ["/repositories"]\n',
    )
    _write_file(
        "apps/web/src/features/repositories/ChangeBatchBoard.tsx",
        "export function ChangeBatchBoard() { return <div>Day08</div>; }\n",
    )
    _write_file(
        "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
        "export function RepositoryOverviewPage() { return <div>Day08 repo page</div>; }\n",
    )
    _write_file(
        ".github/workflows/ci.yml",
        "name: smoke\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    _write_file(
        "scripts/release.ps1",
        "Write-Host 'release'\n",
    )
    _write_file(
        "infra/deploy/main.tf",
        'terraform { required_version = ">= 1.5.0" }\n',
    )
    _write_file(
        "docs/ops/runbook.md",
        "# Runbook\n\nDay08 smoke runbook.\n",
    )
    _write_file(
        ".gitignore",
        "node_modules/\n.tmp/\n",
    )
    _write_file(
        "README.md",
        "# Day08 Smoke Repo\n",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day08 smoke repo")
    _run_git("checkout", "-b", "feature/day08-preflight")

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
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )

    return response.json()


def _create_project(client: Any, *, name: str, summary: str) -> Any:
    return _request_json(
        client,
        "POST",
        "/projects",
        expected_status=201,
        json_body={"name": name, "summary": summary},
    )


def _bind_repository(client: Any, *, project_id: str) -> Any:
    return _request_json(
        client,
        "PUT",
        f"/repositories/projects/{project_id}",
        expected_status=200,
        json_body={
            "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
            "display_name": "Day08 smoke repo",
            "default_base_branch": "main",
        },
    )


def _create_task(
    client: Any,
    *,
    project_id: str,
    title: str,
    input_summary: str,
    acceptance_criteria: list[str],
    depends_on_task_ids: list[str] | None = None,
) -> Any:
    body: dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "input_summary": input_summary,
        "acceptance_criteria": acceptance_criteria,
    }
    if depends_on_task_ids:
        body["depends_on_task_ids"] = depends_on_task_ids

    return _request_json(
        client,
        "POST",
        "/tasks",
        expected_status=201,
        json_body=body,
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
            "summary": f"{title} 摘要。",
            "content": f"# {title}\n\nDay08 smoke deliverable.",
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
    intent_summary: str,
    target_files: list[dict[str, Any]],
    verification_commands: list[str],
    risk_notes: list[str],
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
            "intent_summary": intent_summary,
            "source_summary": "Day08 smoke ????????????????",
            "focus_terms": ["preflight", "risk guard", "day08"],
            "target_files": target_files,
            "expected_actions": [
                "??????",
                "?????????",
            ],
            "risk_notes": risk_notes,
            "verification_commands": verification_commands,
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
        json_body={"change_plan_ids": change_plan_ids},
    )


def _run_preflight(
    client: Any,
    *,
    change_batch_id: str,
    candidate_commands: list[str],
) -> Any:
    return _request_json(
        client,
        "POST",
        f"/repositories/change-batches/{change_batch_id}/preflight",
        expected_status=200,
        json_body={"candidate_commands": candidate_commands},
    )


def _setup_high_risk_project(client: Any) -> dict[str, Any]:
    project = _create_project(
        client,
        name="Day08 High Risk Project",
        summary="Exercise high-risk preflight blocking and manual confirmation.",
    )
    _bind_repository(client, project_id=project["id"])

    task_backend = _create_task(
        client,
        project_id=project["id"],
        title="????????",
        input_summary="???????????????????",
        acceptance_criteria=["?????????", "???????"],
    )
    task_ops = _create_task(
        client,
        project_id=project["id"],
        title="??????????",
        input_summary="??????????????????????",
        acceptance_criteria=["??????", "???????????"],
        depends_on_task_ids=[task_backend["id"]],
    )
    task_docs = _create_task(
        client,
        project_id=project["id"],
        title="???????",
        input_summary="????????????????",
        acceptance_criteria=["??????", "??? Day09+"],
        depends_on_task_ids=[task_ops["id"]],
    )

    deliverable_backend = _create_deliverable(
        client,
        project_id=project["id"],
        task_id=task_backend["id"],
        title="?????????",
    )
    deliverable_ops = _create_deliverable(
        client,
        project_id=project["id"],
        task_id=task_ops["id"],
        title="?????????",
    )
    deliverable_docs = _create_deliverable(
        client,
        project_id=project["id"],
        task_id=task_docs["id"],
        title="???????",
    )

    backend_plan = _create_change_plan(
        client,
        project_id=project["id"],
        task_id=task_backend["id"],
        deliverable_id=deliverable_backend["id"],
        title="??????",
        intent_summary="??????????????????????",
        target_files=[
            {
                "relative_path": "runtime/orchestrator/app/core/db.py",
                "language": "python",
                "file_type": "py",
                "rationale": "??????????",
                "match_reasons": ["backend", "core"],
            },
            {
                "relative_path": "runtime/orchestrator/app/services/change_batch_service.py",
                "language": "python",
                "file_type": "py",
                "rationale": "??????",
                "match_reasons": ["service", "batch"],
            },
        ],
        verification_commands=[
            "python -m py_compile runtime/orchestrator/app/core/db.py",
            'git commit -m "dangerous"',
        ],
        risk_notes=["??????", "???????? Git ???"],
    )
    ops_plan = _create_change_plan(
        client,
        project_id=project["id"],
        task_id=task_ops["id"],
        deliverable_id=deliverable_ops["id"],
        title="????????",
        intent_summary="????????????????? Day08 ?????",
        target_files=[
            {
                "relative_path": ".github/workflows/ci.yml",
                "language": "yaml",
                "file_type": "yml",
                "rationale": "CI ?????",
                "match_reasons": ["workflow", "ci"],
            },
            {
                "relative_path": "scripts/release.ps1",
                "language": "powershell",
                "file_type": "ps1",
                "rationale": "????",
                "match_reasons": ["script", "release"],
            },
            {
                "relative_path": "infra/deploy/main.tf",
                "language": "terraform",
                "file_type": "tf",
                "rationale": "??????",
                "match_reasons": ["infra", "deploy"],
            },
        ],
        verification_commands=[
            "git push origin main",
            "git reset --hard HEAD~1",
        ],
        risk_notes=["??????", "????? Git ???"],
    )
    docs_plan = _create_change_plan(
        client,
        project_id=project["id"],
        task_id=task_docs["id"],
        deliverable_id=deliverable_docs["id"],
        title="??????",
        intent_summary="????????????????? Day08 ???????",
        target_files=[
            {
                "relative_path": ".gitignore",
                "language": "text",
                "file_type": "gitignore",
                "rationale": "??????",
                "match_reasons": ["ignore", "scope"],
            },
            {
                "relative_path": "docs/ops/runbook.md",
                "language": "markdown",
                "file_type": "md",
                "rationale": "????",
                "match_reasons": ["docs", "ops"],
            },
        ],
        verification_commands=["cmd /c echo review only"],
        risk_notes=["??????", "????????????"],
    )

    change_batch = _create_change_batch(
        client,
        project_id=project["id"],
        change_plan_ids=[backend_plan["id"], ops_plan["id"], docs_plan["id"]],
    )
    preflight = _run_preflight(
        client,
        change_batch_id=change_batch["id"],
        candidate_commands=[
            "git clean -fd",
            "Remove-Item -Recurse -Force runtime/data",
        ],
    )

    return {
        "project": project,
        "change_batch": change_batch,
        "preflight": preflight,
    }


def _setup_low_risk_project(client: Any) -> dict[str, Any]:
    project = _create_project(
        client,
        name="Day08 Low Risk Project",
        summary="Exercise low-risk preflight ready-for-execution path.",
    )
    _bind_repository(client, project_id=project["id"])

    task_service = _create_task(
        client,
        project_id=project["id"],
        title="???????",
        input_summary="??????????? ChangeBatch ???",
        acceptance_criteria=["?????", "???????"],
    )
    task_frontend = _create_task(
        client,
        project_id=project["id"],
        title="???????",
        input_summary="??????????????",
        acceptance_criteria=["?????????", "??????????"],
        depends_on_task_ids=[task_service["id"]],
    )

    deliverable_service = _create_deliverable(
        client,
        project_id=project["id"],
        task_id=task_service["id"],
        title="?????????",
    )
    deliverable_frontend = _create_deliverable(
        client,
        project_id=project["id"],
        task_id=task_frontend["id"],
        title="?????????",
    )

    service_plan = _create_change_plan(
        client,
        project_id=project["id"],
        task_id=task_service["id"],
        deliverable_id=deliverable_service["id"],
        title="???????",
        intent_summary="????????????????",
        target_files=[
            {
                "relative_path": "runtime/orchestrator/app/services/change_batch_service.py",
                "language": "python",
                "file_type": "py",
                "rationale": "???????",
                "match_reasons": ["service"],
            },
            {
                "relative_path": "runtime/orchestrator/app/services/preflight_note.py",
                "language": "python",
                "file_type": "py",
                "rationale": "普通服务层说明文件",
                "match_reasons": ["service", "note"],
            },
        ],
        verification_commands=[
            "python -m py_compile runtime/orchestrator/app/services/change_batch_service.py",
        ],
        risk_notes=["??????", "???????"],
    )
    frontend_plan = _create_change_plan(
        client,
        project_id=project["id"],
        task_id=task_frontend["id"],
        deliverable_id=deliverable_frontend["id"],
        title="??????",
        intent_summary="?????????????????",
        target_files=[
            {
                "relative_path": "apps/web/src/features/repositories/ChangeBatchBoard.tsx",
                "language": "typescript",
                "file_type": "tsx",
                "rationale": "???????",
                "match_reasons": ["frontend", "board"],
            },
            {
                "relative_path": "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
                "language": "typescript",
                "file_type": "tsx",
                "rationale": "?????",
                "match_reasons": ["frontend", "overview"],
            },
        ],
        verification_commands=["cmd /c npm run build"],
        risk_notes=["??? Day08 ??", "??? Day09+"],
    )

    change_batch = _create_change_batch(
        client,
        project_id=project["id"],
        change_plan_ids=[service_plan["id"], frontend_plan["id"]],
    )
    preflight = _run_preflight(
        client,
        change_batch_id=change_batch["id"],
        candidate_commands=["python -m py_compile runtime/orchestrator/app/api/routes/repositories.py"],
    )

    return {
        "project": project,
        "change_batch": change_batch,
        "preflight": preflight,
    }


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        high_risk = _setup_high_risk_project(client)
        low_risk = _setup_low_risk_project(client)

        high_findings = high_risk["preflight"]["preflight"]["findings"]
        high_categories = {item["category"] for item in high_findings}
        _assert(
            high_risk["preflight"]["preflight"]["status"] == "blocked_requires_confirmation",
            "High-risk batches should be blocked and redirected to manual confirmation.",
        )
        _assert(
            high_risk["preflight"]["preflight"]["manual_confirmation_required"] is True,
            "High-risk preflight should require manual confirmation.",
        )
        _assert(
            {
                "sensitive_directory",
                "sensitive_file",
                "dangerous_command",
                "wide_change",
            }.issubset(high_categories),
            "High-risk preflight should emit standardized categories for directory, file, command and wide-change risks.",
        )
        _assert(
            high_risk["preflight"]["preflight"]["critical_risk_count"] >= 1,
            "High-risk batch should include at least one critical command finding.",
        )

        high_inbox = _request_json(
            client,
            "GET",
            f"/approvals/projects/{high_risk['project']['id']}/repository-preflight",
            expected_status=200,
        )
        _assert(
            high_inbox["pending_confirmations"] == 1,
            "High-risk project should surface one pending manual-confirmation item.",
        )

        high_detail = _request_json(
            client,
            "GET",
            f"/approvals/repository-preflight/{high_risk['change_batch']['id']}",
            expected_status=200,
        )
        _assert(
            high_detail["preflight"]["status"] == "blocked_requires_confirmation",
            "Approval-facing preflight detail should preserve the blocked status.",
        )

        high_confirmed = _request_json(
            client,
            "POST",
            f"/approvals/repository-preflight/{high_risk['change_batch']['id']}/actions",
            expected_status=200,
            json_body={
                "action": "approve",
                "actor_name": "??",
                "summary": "?????????????????????",
                "comment": "Day08 ???????????????????",
                "highlighted_risks": ["?? Git ????????"],
            },
        )
        _assert(
            high_confirmed["preflight"]["status"] == "manual_confirmed",
            "Manual confirmation should update the high-risk batch into manual_confirmed.",
        )
        _assert(
            high_confirmed["preflight"]["ready_for_execution"] is True,
            "Manual approval should produce a ready_for_execution result without auto-executing anything.",
        )

        low_preflight = low_risk["preflight"]["preflight"]
        _assert(
            low_preflight["status"] == "ready_for_execution",
            "Low-risk batches should receive the ready_for_execution preflight result.",
        )
        _assert(
            low_preflight["manual_confirmation_required"] is False,
            "Low-risk batches should not require manual confirmation.",
        )
        _assert(
            low_preflight["finding_count"] == 0,
            "The low-risk scenario should stay within the clean preflight path.",
        )

        low_inbox = _request_json(
            client,
            "GET",
            f"/approvals/projects/{low_risk['project']['id']}/repository-preflight",
            expected_status=200,
        )
        _assert(
            low_inbox["ready_batches"] == 1 and low_inbox["pending_confirmations"] == 0,
            "Low-risk project should surface one ready batch and no pending confirmation.",
        )

        high_timeline = _request_json(
            client,
            "GET",
            f"/projects/{high_risk['project']['id']}/timeline",
            expected_status=200,
        )
        _assert(
            any(event["event_type"] == "preflight" for event in high_timeline["events"]),
            "Project timeline should include Day08 preflight events for the high-risk project.",
        )

        low_timeline = _request_json(
            client,
            "GET",
            f"/projects/{low_risk['project']['id']}/timeline",
            expected_status=200,
        )
        _assert(
            any(event["event_type"] == "preflight" for event in low_timeline["events"]),
            "Project timeline should include Day08 preflight events for the low-risk project.",
        )

    report = {
        "high_risk_project_id": high_risk["project"]["id"],
        "high_risk_change_batch_id": high_risk["change_batch"]["id"],
        "high_risk_status_after_manual_confirmation": high_confirmed["preflight"]["status"],
        "high_risk_categories": sorted(high_categories),
        "low_risk_project_id": low_risk["project"]["id"],
        "low_risk_change_batch_id": low_risk["change_batch"]["id"],
        "low_risk_status": low_preflight["status"],
        "timeline_event_types": sorted(
            {
                event["event_type"]
                for event in [*high_timeline["events"], *low_timeline["events"]]
            }
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
