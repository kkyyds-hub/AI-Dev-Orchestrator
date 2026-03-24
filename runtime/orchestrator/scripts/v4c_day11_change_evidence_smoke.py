"""V4-C Day11 smoke checks for repository diff summaries and acceptance evidence packs."""

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
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day11-change-evidence-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day11-change-evidence"


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
        "apps/web/package.json",
        json.dumps(
            {
                "name": "day11-smoke-web",
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
        "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
        "export function RepositoryOverviewPage() { return <div>Day11 Repo Page</div>; }\n",
    )
    _write_file(
        "runtime/orchestrator/app/services/verification_run_service.py",
        '"""Day11 smoke verification run service."""\n\nSERVICE_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/deliverables.py",
        '"""Day11 smoke deliverable route."""\n\nROUTES = ["/deliverables"]\n',
    )
    _write_file(
        "README.md",
        "# Day11 Smoke Repo\n",
    )
    _write_file(
        ".gitignore",
        "node_modules/\n.tmp/\n",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day11 smoke repo")

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


def _create_project(client: Any) -> Any:
    return _request_json(
        client,
        "POST",
        "/projects",
        expected_status=201,
        json_body={
            "name": "Day11 代码差异证据项目",
            "summary": "验证 Day11 代码差异摘要与验收证据包。",
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
            "display_name": "Day11 smoke repo",
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
                "可聚合文件差异统计",
                "可回溯交付件、验证、审批上下文",
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
            "summary": "Day11 烟测交付件摘要。",
            "content": "# Day11\n\nSmoke deliverable.",
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
            "intent_summary": f"{title} 的 Day11 烟测计划。",
            "source_summary": "Day11 smoke 来源摘要。",
            "focus_terms": ["diff", "evidence", "day11"],
            "target_files": target_files,
            "expected_actions": [
                "聚合仓库差异统计",
                "生成验收证据包",
            ],
            "risk_notes": [
                "Day11 只冻结差异与证据汇总，不进入 Day12 回退重做。",
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
            "title": "Day11 差异证据批次",
            "change_plan_ids": change_plan_ids,
        },
    )


def _record_verification_run(
    client: Any,
    *,
    project_id: str,
    change_plan_id: str,
    change_batch_id: str,
    status: str,
    output_summary: str,
    verification_template_id: str | None = None,
    command: str | None = None,
    working_directory: str | None = None,
    failure_category: str | None = None,
    duration_seconds: float = 0.0,
) -> Any:
    body: dict[str, Any] = {
        "project_id": project_id,
        "change_plan_id": change_plan_id,
        "change_batch_id": change_batch_id,
        "status": status,
        "duration_seconds": duration_seconds,
        "output_summary": output_summary,
    }
    if verification_template_id is not None:
        body["verification_template_id"] = verification_template_id
    if command is not None:
        body["command"] = command
    if working_directory is not None:
        body["working_directory"] = working_directory
    if failure_category is not None:
        body["failure_category"] = failure_category

    return _request_json(
        client,
        "POST",
        "/runs/verification",
        expected_status=201,
        json_body=body,
    )


def _create_approval(client: Any, *, deliverable_id: str) -> Any:
    return _request_json(
        client,
        "POST",
        "/approvals",
        expected_status=201,
        json_body={
            "deliverable_id": deliverable_id,
            "requester_role_code": "product_manager",
            "request_note": "请核对 Day11 差异视图是否能支撑老板验收。",
            "due_in_hours": 8,
        },
    )


def _apply_approval_action(client: Any, *, approval_id: str) -> Any:
    return _request_json(
        client,
        "POST",
        f"/approvals/{approval_id}/actions",
        expected_status=200,
        json_body={
            "action": "request_changes",
            "actor_name": "老板",
            "summary": "需补全按文件维度的关键差异摘要。",
            "comment": "请确保可从审批页反查证据包。",
            "highlighted_risks": ["差异统计可能遗漏未跟踪文件"],
            "requested_changes": ["补全关键文件清单并关联审批上下文"],
        },
    )


def _apply_workspace_changes() -> None:
    _write_file(
        "runtime/orchestrator/app/services/verification_run_service.py",
        (
            '"""Day11 smoke verification run service."""\n\n'
            "SERVICE_READY = True\n"
            "CHANGE_EVIDENCE_READY = True\n"
        ),
    )
    _write_file(
        "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
        (
            "export function RepositoryOverviewPage() {\n"
            "  return <div>Day11 Diff Summary + Change Evidence</div>;\n"
            "}\n"
        ),
    )
    _write_file(
        "runtime/orchestrator/app/domain/change_evidence.py",
        '"""Day11 smoke untracked file."""\n\nEVIDENCE_DOMAIN = True\n',
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])

        baseline = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
        )
        template_ids_by_category = {
            template["category"]: template["id"]
            for template in baseline["templates"]
        }
        _assert(
            {"build", "test", "lint", "typecheck"} == set(template_ids_by_category),
            "Day11 smoke requires the Day09 verification baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="聚合后端差异与证据",
            input_summary="补齐 Day11 差异摘要与证据包服务。",
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="展示差异与证据面板",
            input_summary="补齐 Day11 仓库差异视图和交付件证据面板。",
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day11 后端方案",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day11 前端方案",
        )

        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day11 后端差异证据草案",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/services/verification_run_service.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐 Day11 后端聚合服务",
                    "match_reasons": ["service", "day11"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/deliverables.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐 Day11 证据包接口",
                    "match_reasons": ["api", "day11"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/services/verification_run_service.py",
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
            title="Day11 前端差异视图草案",
            target_files=[
                {
                    "relative_path": "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "补齐 Day11 仓库差异视图入口",
                    "match_reasons": ["ui", "day11"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/api/routes/deliverables.py",
            ],
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

        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            status="passed",
            output_summary="Day11 后端验证通过。",
            duration_seconds=10.2,
        )
        time.sleep(0.02)
        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_frontend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["test"],
            status="failed",
            failure_category="command_failed",
            output_summary="Day11 前端验证失败，已记录归因。",
            duration_seconds=21.7,
        )
        time.sleep(0.02)
        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            command="python -m py_compile runtime/orchestrator/app/services/verification_run_service.py",
            working_directory=".",
            status="skipped",
            failure_category="precheck_blocked",
            output_summary="Day11 命令已登记，但本轮预检阻断。",
            duration_seconds=0.0,
        )

        approval = _create_approval(client, deliverable_id=deliverable_backend["id"])
        approval = _apply_approval_action(client, approval_id=approval["id"])

        _apply_workspace_changes()

        project_evidence = _request_json(
            client,
            "GET",
            (
                f"/deliverables/projects/{project['id']}/change-evidence"
                f"?change_batch_id={change_batch['id']}"
            ),
            expected_status=200,
        )
        deliverable_evidence = _request_json(
            client,
            "GET",
            f"/deliverables/{deliverable_backend['id']}/change-evidence",
            expected_status=200,
        )
        approval_evidence = _request_json(
            client,
            "GET",
            f"/deliverables/approvals/{approval['id']}/change-evidence",
            expected_status=200,
        )

        diff_metrics = project_evidence["diff_summary"]["metrics"]
        _assert(
            project_evidence["selected_change_batch_id"] == change_batch["id"],
            "Project evidence should bind to the requested ChangeBatch.",
        )
        _assert(
            diff_metrics["changed_file_count"] >= 2,
            "Day11 project evidence should expose changed files.",
        )
        _assert(
            project_evidence["diff_summary"]["key_files"],
            "Day11 project evidence should expose key files.",
        )
        _assert(
            any(
                row["relative_path"]
                == "runtime/orchestrator/app/services/verification_run_service.py"
                for row in project_evidence["diff_summary"]["files"]
            ),
            "Diff summary should include backend service file changes.",
        )
        _assert(
            any(
                row["relative_path"] == "runtime/orchestrator/app/domain/change_evidence.py"
                and row["change_kind"] == "untracked"
                for row in project_evidence["diff_summary"]["files"]
            ),
            "Diff summary should include untracked evidence-domain file changes.",
        )
        _assert(
            len(project_evidence["plan_items"]) == 2,
            "Evidence package should include two ChangePlan snapshots.",
        )
        _assert(
            project_evidence["verification_summary"]["total_runs"] == 3,
            "Evidence package should aggregate verification run counts.",
        )
        _assert(
            project_evidence["verification_summary"]["failed_runs"] == 1,
            "Evidence package should preserve failed verification counts.",
        )
        _assert(
            deliverable_backend["id"]
            in project_evidence["reverse_lookup"]["deliverable_ids"],
            "Project evidence should support deliverable reverse lookup.",
        )
        _assert(
            approval["id"] in project_evidence["reverse_lookup"]["approval_ids"],
            "Project evidence should support approval reverse lookup.",
        )
        _assert(
            any(
                snapshot["snapshot_kind"] == "change_batch"
                for snapshot in project_evidence["snapshots"]
            ),
            "Evidence package should contain a ChangeBatch snapshot.",
        )
        _assert(
            any(
                snapshot["snapshot_kind"] == "approval"
                for snapshot in project_evidence["snapshots"]
            ),
            "Evidence package should contain an approval snapshot.",
        )

        _assert(
            deliverable_evidence["selected_deliverable_id"] == deliverable_backend["id"],
            "Deliverable evidence should mark the selected deliverable.",
        )
        _assert(
            any(item["selected"] for item in deliverable_evidence["deliverables"]),
            "Deliverable evidence should highlight selected deliverable context.",
        )
        _assert(
            deliverable_backend["id"]
            in deliverable_evidence["reverse_lookup"]["deliverable_ids"],
            "Deliverable evidence should preserve reverse lookup IDs.",
        )

        _assert(
            approval_evidence["selected_approval_id"] == approval["id"],
            "Approval evidence should mark the selected approval.",
        )
        _assert(
            any(item["selected"] for item in approval_evidence["approvals"]),
            "Approval evidence should highlight selected approval context.",
        )
        _assert(
            approval["id"] in approval_evidence["reverse_lookup"]["approval_ids"],
            "Approval evidence should preserve reverse lookup IDs.",
        )

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "deliverable_id": deliverable_backend["id"],
        "approval_id": approval["id"],
        "project_package_key": project_evidence["package_key"],
        "deliverable_package_key": deliverable_evidence["package_key"],
        "approval_package_key": approval_evidence["package_key"],
        "changed_file_count": diff_metrics["changed_file_count"],
        "key_file_count": diff_metrics["key_file_count"],
        "verification_total_runs": project_evidence["verification_summary"]["total_runs"],
        "snapshot_count": len(project_evidence["snapshots"]),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
