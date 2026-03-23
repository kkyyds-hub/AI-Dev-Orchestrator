"""V4-C Day09 smoke checks for repository verification baselines and template references."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day09-repository-verification-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day09-verification-baseline"


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
                "name": "day09-smoke-web",
                "private": True,
                "scripts": {
                    "build": "echo build",
                },
                "devDependencies": {
                    "typescript": "^5.8.2",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_file(
        "apps/web/src/features/repositories/RepositoryVerificationPanel.tsx",
        "export function RepositoryVerificationPanel() { return <div>Day09</div>; }\n",
    )
    _write_file(
        "runtime/orchestrator/app/services/repository_verification_service.py",
        '"""Day09 smoke verification service."""\n\nSERVICE_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        '"""Day09 smoke repository route."""\n\nROUTES = ["/repositories"]\n',
    )
    _write_file(
        "runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py",
        'print("day08 smoke placeholder")\n',
    )
    _write_file(
        ".gitignore",
        "node_modules/\n.tmp/\n",
    )
    _write_file(
        "README.md",
        "# Day09 Smoke Repo\n",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day09 smoke repo")

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
            "name": "Day09 验证基线烟测项目",
            "summary": "验证 Day09 仓库验证模板与项目命令基线。",
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
            "display_name": "Day09 smoke repo",
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
                "仓库级 build / test / lint / typecheck 模板可查询",
                "ChangePlan 与 ChangeBatch 能引用 Day09 模板",
            ],
        },
    )


def _create_deliverable(
    client: Any,
    *,
    project_id: str,
    task_id: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/deliverables",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "type": "code_plan",
            "title": "Day09 验证模板方案",
            "stage": "planning",
            "created_by_role_code": "engineer",
            "summary": "Day09 烟测交付件摘要。",
            "content": "# Day09\n\nSmoke deliverable.",
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
            "intent_summary": intent_summary,
            "source_summary": "Day09 smoke 来源摘要。",
            "focus_terms": ["verification", "baseline", "day09"],
            "target_files": [
                {
                    "relative_path": "runtime/orchestrator/app/services/repository_verification_service.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐 Day09 服务层",
                    "match_reasons": ["service", "day09"],
                },
                {
                    "relative_path": "apps/web/src/features/repositories/RepositoryVerificationPanel.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "补齐仓库页展示",
                    "match_reasons": ["ui", "day09"],
                },
            ],
            "expected_actions": [
                "持久化 Day09 验证模板",
                "让 ChangePlan 与 ChangeBatch 能引用模板",
            ],
            "risk_notes": [
                "Day09 仅冻结命令基线，不执行验证运行",
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
            "title": "Day09 基线批次",
            "change_plan_ids": change_plan_ids,
        },
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])

        auto_seeded_baseline = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
        )
        _assert(
            auto_seeded_baseline["template_count"] == 4,
            "Day09 baseline should auto-seed four verification categories.",
        )
        _assert(
            {template["category"] for template in auto_seeded_baseline["templates"]}
            == {"build", "test", "lint", "typecheck"},
            "Auto-seeded Day09 baseline should cover build / test / lint / typecheck.",
        )
        _assert(
            auto_seeded_baseline["last_updated_at"] is not None,
            "Auto-seeded baseline should expose last_updated_at.",
        )

        template_ids_by_category = {
            template["category"]: template["id"]
            for template in auto_seeded_baseline["templates"]
        }

        updated_baseline = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
            json_body={
                "templates": [
                    {
                        "id": template_ids_by_category["build"],
                        "category": "build",
                        "name": "Smoke 构建",
                        "command": "npm run build",
                        "working_directory": "apps/web",
                        "timeout_seconds": 720,
                        "enabled_by_default": True,
                        "description": "Day09 smoke build baseline.",
                    },
                    {
                        "id": template_ids_by_category["test"],
                        "category": "test",
                        "name": "Smoke 烟测",
                        "command": "python runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py",
                        "working_directory": ".",
                        "timeout_seconds": 900,
                        "enabled_by_default": True,
                        "description": "Day09 smoke test baseline.",
                    },
                    {
                        "id": template_ids_by_category["lint"],
                        "category": "lint",
                        "name": "Smoke Lint",
                        "command": "python -m compileall -q runtime/orchestrator/app runtime/orchestrator/scripts",
                        "working_directory": ".",
                        "timeout_seconds": 480,
                        "enabled_by_default": True,
                        "description": "Day09 smoke lint baseline.",
                    },
                    {
                        "id": template_ids_by_category["typecheck"],
                        "category": "typecheck",
                        "name": "Smoke Typecheck",
                        "command": "npx tsc --noEmit",
                        "working_directory": "apps/web",
                        "timeout_seconds": 480,
                        "enabled_by_default": False,
                        "description": "Day09 smoke typecheck baseline.",
                    },
                ]
            },
        )
        _assert(
            updated_baseline["templates"][0]["name"] == "Smoke 构建",
            "Baseline PUT should persist the updated template content.",
        )

        task = _create_task(
            client,
            project_id=project["id"],
            title="补齐验证模板基线",
            input_summary="把仓库级验证模板沉淀到 Day09 基线，并让 ChangePlan 可引用。",
        )
        task_two = _create_task(
            client,
            project_id=project["id"],
            title="补齐批次模板引用",
            input_summary="让 ChangeBatch 继承并展示 Day09 模板命令。",
        )
        deliverable = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task["id"],
        )
        deliverable_two = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_two["id"],
        )
        change_plan = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task["id"],
            deliverable_id=deliverable["id"],
            title="Day09 命令基线草案",
            intent_summary="让计划与批次都能引用仓库级验证模板。",
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/services/repository_verification_service.py",
            ],
            verification_template_ids=[
                template_ids_by_category["build"],
                template_ids_by_category["typecheck"],
            ],
        )
        change_plan_two = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_two["id"],
            deliverable_id=deliverable_two["id"],
            title="Day09 批次引用草案",
            intent_summary="补齐 ChangeBatch 对 Day09 模板的继承展示。",
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/api/routes/repositories.py",
            ],
            verification_template_ids=[template_ids_by_category["lint"]],
        )
        latest_version = change_plan["latest_version"]
        _assert(
            len(latest_version["verification_templates"]) == 2,
            "ChangePlan should preserve Day09 verification-template references.",
        )
        _assert(
            latest_version["verification_commands"]
            == [
                "python -m py_compile runtime/orchestrator/app/services/repository_verification_service.py"
            ],
            "ChangePlan should keep manual verification commands without duplicating template commands.",
        )

        change_batch = _create_change_batch(
            client,
            project_id=project["id"],
            change_plan_ids=[change_plan["id"], change_plan_two["id"]],
        )
        change_batch_detail = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}",
            expected_status=200,
        )
        task_views = change_batch_detail["tasks"]
        first_task_view = next(
            item for item in task_views if item["change_plan_id"] == change_plan["id"]
        )
        second_task_view = next(
            item for item in task_views if item["change_plan_id"] == change_plan_two["id"]
        )
        _assert(
            len(first_task_view["verification_templates"]) == 2
            and len(second_task_view["verification_templates"]) == 1,
            "ChangeBatch detail should expose the Day09 template references inherited from both ChangePlans.",
        )
        _assert(
            {
                "python -m py_compile runtime/orchestrator/app/services/repository_verification_service.py",
                "npm run build",
                "npx tsc --noEmit",
            }.issubset(set(first_task_view["verification_commands"])),
            "The first ChangeBatch task should merge manual commands with its referenced template commands.",
        )
        _assert(
            {
                "python -m py_compile runtime/orchestrator/app/api/routes/repositories.py",
                "python -m compileall -q runtime/orchestrator/app runtime/orchestrator/scripts",
            }.issubset(set(second_task_view["verification_commands"])),
            "The second ChangeBatch task should merge its manual command with the referenced lint template.",
        )
        _assert(
            change_batch_detail["verification_command_count"] == 5,
            "ChangeBatch summary should count the merged Day09 verification-command baseline.",
        )

    report = {
        "project_id": project["id"],
        "configured_categories": updated_baseline["configured_categories"],
        "change_plan_id": change_plan["id"],
        "change_plan_two_id": change_plan_two["id"],
        "change_batch_id": change_batch["id"],
        "change_plan_template_names": [
            template["name"] for template in latest_version["verification_templates"]
        ],
        "change_batch_verification_commands": {
            first_task_view["change_plan_title"]: first_task_view["verification_commands"],
            second_task_view["change_plan_title"]: second_task_view["verification_commands"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
