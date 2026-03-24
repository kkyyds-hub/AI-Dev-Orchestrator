"""V4-C Day10 smoke checks for structured verification-run records and repository view data."""

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
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day10-verification-run-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day10-verification-run"


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
                "name": "day10-smoke-web",
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
        "apps/web/src/features/run-log/VerificationRunPanel.tsx",
        "export function VerificationRunPanel() { return <div>Day10</div>; }\n",
    )
    _write_file(
        "runtime/orchestrator/app/domain/verification_run.py",
        '"""Day10 smoke verification run domain."""\n\nDOMAIN_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/services/verification_run_service.py",
        '"""Day10 smoke verification run service."""\n\nSERVICE_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/runs.py",
        '"""Day10 smoke run route."""\n\nROUTES = ["/runs/verification"]\n',
    )
    _write_file(
        "README.md",
        "# Day10 Smoke Repo\n",
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
    _run_git("commit", "-m", "init day10 smoke repo")

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
            "name": "Day10 验证运行记录项目",
            "summary": "验证 Day10 结构化 VerificationRun 的最小烟测。",
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
            "display_name": "Day10 smoke repo",
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
                "验证运行记录可关联仓库、ChangePlan、ChangeBatch",
                "验证运行结果可记录 passed / failed / skipped 与失败类别",
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
            "summary": "Day10 烟测交付件摘要。",
            "content": "# Day10\n\nSmoke deliverable.",
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
            "intent_summary": f"{title} 的 Day10 烟测计划。",
            "source_summary": "Day10 smoke 来源摘要。",
            "focus_terms": ["verification", "run", "day10"],
            "target_files": target_files,
            "expected_actions": [
                "沉淀结构化 VerificationRun 记录",
                "让仓库页可展示最新验证结果",
            ],
            "risk_notes": [
                "Day10 只冻结验证运行记录，不提前进入 Day11 差异视图",
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
            "title": "Day10 验证运行批次",
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
            "Day10 smoke requires the Day09 verification baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="沉淀后端验证运行记录",
            input_summary="补齐 VerificationRun 领域、仓储与接口。",
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="展示仓库验证结果面板",
            input_summary="让仓库页可以看到最新验证运行结果。",
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day10 后端方案",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day10 前端方案",
        )

        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day10 后端验证记录草案",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/domain/verification_run.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "沉淀 Day10 领域模型",
                    "match_reasons": ["domain", "day10"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/services/verification_run_service.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐 Day10 服务层",
                    "match_reasons": ["service", "day10"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/domain/verification_run.py",
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
            title="Day10 前端验证面板草案",
            target_files=[
                {
                    "relative_path": "apps/web/src/features/run-log/VerificationRunPanel.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "补齐 Day10 仓库视图面板",
                    "match_reasons": ["ui", "day10"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/runs.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "提供 Day10 读取接口",
                    "match_reasons": ["api", "day10"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/api/routes/runs.py",
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

        passed_run = _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            status="passed",
            output_summary="Build 模板验证通过，已生成结构化记录。",
            duration_seconds=12.8,
        )
        time.sleep(0.02)
        failed_run = _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_frontend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["test"],
            status="failed",
            failure_category="command_failed",
            output_summary="Smoke test 模板执行失败，已归因为命令失败。",
            duration_seconds=31.4,
        )
        time.sleep(0.02)
        skipped_run = _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            command="python -m py_compile runtime/orchestrator/app/domain/verification_run.py",
            working_directory=".",
            status="skipped",
            failure_category="precheck_blocked",
            output_summary="命令已登记但本轮因 Day08 预检阻断而跳过。",
            duration_seconds=0.0,
        )

        project_feed = _request_json(
            client,
            "GET",
            f"/runs/verification/projects/{project['id']}?limit=10",
            expected_status=200,
        )
        filtered_feed = _request_json(
            client,
            "GET",
            (
                f"/runs/verification/projects/{project['id']}"
                f"?change_batch_id={change_batch['id']}&limit=10"
            ),
            expected_status=200,
        )

        _assert(project_feed["total_runs"] == 3, "Project feed should expose three runs.")
        _assert(
            project_feed["status_counts"] == {"passed": 1, "failed": 1, "skipped": 1},
            "Project feed should aggregate passed / failed / skipped counts.",
        )
        _assert(
            project_feed["latest_run"]["id"] == skipped_run["id"],
            "Latest verification result should point to the most recently recorded run.",
        )
        _assert(
            filtered_feed["runs"][0]["change_batch_id"] == change_batch["id"],
            "Filtered feed should keep the requested ChangeBatch association.",
        )
        _assert(
            passed_run["verification_template_name"] is not None
            and passed_run["command_source"] == "template",
            "Template-backed verification runs should expose template metadata.",
        )
        _assert(
            failed_run["failure_category"] == "command_failed",
            "Failed verification runs should preserve the failure category.",
        )
        _assert(
            skipped_run["command_source"] == "manual"
            and skipped_run["failure_category"] == "precheck_blocked",
            "Skipped manual verification runs should preserve the skip attribution.",
        )
        _assert(
            filtered_feed["runs"][0]["change_plan_title"] == change_plan_backend["title"]
            or filtered_feed["runs"][0]["change_plan_title"]
            == change_plan_frontend["title"],
            "Verification feed rows should expose the linked ChangePlan title.",
        )

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "recorded_run_ids": [passed_run["id"], failed_run["id"], skipped_run["id"]],
        "status_counts": project_feed["status_counts"],
        "latest_status": project_feed["latest_run"]["status"],
        "latest_summary": project_feed["latest_run"]["output_summary"],
        "template_names": [
            run["verification_template_name"]
            for run in project_feed["runs"]
            if run["verification_template_name"] is not None
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
