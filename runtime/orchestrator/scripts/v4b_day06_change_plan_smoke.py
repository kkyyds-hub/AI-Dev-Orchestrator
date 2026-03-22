"""V4-B Day06 smoke checks for structured change-plan draft mapping."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day06-change-plan-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day06-change-plan"


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


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    (
        SMOKE_REPOSITORY_ROOT / "runtime" / "orchestrator" / "app" / "services"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "runtime" / "orchestrator" / "app" / "api" / "routes"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "apps" / "web" / "src" / "features" / "projects"
    ).mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake").mkdir(parents=True, exist_ok=True)

    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "services"
        / "change_plan_service.py"
    ).write_text(
        "\n".join(
            [
                '"""Day06 smoke target service."""',
                "",
                "class ChangePlanService:",
                "    def build_change_plan(self):",
                "        return {'mode': 'draft'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "api"
        / "routes"
        / "planning.py"
    ).write_text(
        "\n".join(
            [
                '"""Day06 smoke target route."""',
                "",
                "def register_change_plan_routes(router):",
                "    router.append('/planning/projects/{project_id}/change-plans')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "apps"
        / "web"
        / "src"
        / "features"
        / "projects"
        / "ChangePlanDrawer.tsx"
    ).write_text(
        "\n".join(
            [
                "export function ChangePlanDrawer() {",
                "  return <div>Day06 ChangePlan drawer</div>;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "day06-plan.md").write_text(
        "# Day06\n\nChangePlan draft mapping smoke repo.\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake" / "ignored.js").write_text(
        "console.log('ignored');\n",
        encoding="utf-8",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day06 smoke repo")
    _run_git("checkout", "-b", "feature/day06-change-plan")

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


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "Day06 ChangePlan Project",
                "summary": "Map tasks, deliverables and candidate files into structured change-plan drafts.",
            },
        )
        _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "Day06 smoke repo",
                "default_base_branch": "main",
            },
        )

        task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "为 Day06 生成 ChangePlan 草案",
                "input_summary": "需要把 Day05 的候选文件与交付件映射成结构化变更计划草案。",
                "acceptance_criteria": [
                    "可创建与查看变更计划草案",
                    "可追加新版本并保留时间线",
                ],
            },
        )
        deliverable = _request_json(
            client,
            "POST",
            "/deliverables",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "type": "code_plan",
                "title": "Day06 变更计划交付件",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "记录 Day06 ChangePlan 草案。",
                "content": "# ChangePlan\n\n初始草案。",
                "content_format": "markdown",
                "source_task_id": task["id"],
            },
        )

        locator_result = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "task_id": task["id"],
                "keywords": ["ChangePlan", "planning", "drawer"],
                "file_types": ["py", "tsx"],
                "limit": 6,
            },
        )
        selected_paths = [
            candidate["relative_path"] for candidate in locator_result["candidates"][:3]
        ]
        _assert(
            "runtime/orchestrator/app/services/change_plan_service.py" in selected_paths,
            "Day06 locator search should find the backend change-plan service file.",
        )
        _assert(
            "apps/web/src/features/projects/ChangePlanDrawer.tsx" in selected_paths,
            "Day06 locator search should find the frontend ChangePlan drawer file.",
        )

        context_pack = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/context-pack",
            expected_status=200,
            json_body={
                "task_id": task["id"],
                "selected_paths": selected_paths,
                "max_total_bytes": 1600,
                "max_bytes_per_file": 700,
            },
        )
        target_files = [
            {
                "relative_path": entry["relative_path"],
                "language": entry["language"],
                "file_type": entry["file_type"],
                "rationale": None,
                "match_reasons": entry["match_reasons"],
            }
            for entry in context_pack["entries"]
        ]

        created_plan = _request_json(
            client,
            "POST",
            f"/planning/projects/{project['id']}/change-plans",
            expected_status=201,
            json_body={
                "task_id": task["id"],
                "title": "Day06 ChangePlan 草案",
                "primary_deliverable_id": deliverable["id"],
                "related_deliverable_ids": [deliverable["id"]],
                "intent_summary": "先冻结任务到文件的映射和验证命令引用，供后续 Day07 使用。",
                "source_summary": context_pack["source_summary"],
                "focus_terms": context_pack["focus_terms"],
                "target_files": target_files,
                "expected_actions": [
                    "新增 ChangePlan 持久化模型",
                    "补 planning 路由与前端抽屉",
                ],
                "risk_notes": [
                    "不要提前进入 Day07 变更批次",
                    "不要加入 Day08 风险守卫",
                ],
                "verification_commands": [
                    "python -m py_compile runtime/orchestrator/app/services/change_plan_service.py",
                    "npm run build",
                ],
                "context_pack_generated_at": context_pack["generated_at"],
            },
        )
        _assert(
            created_plan["current_version_number"] == 1,
            "New Day06 change-plan threads should start at version 1.",
        )
        _assert(
            len(created_plan["latest_version"]["target_files"]) >= 2,
            "Day06 draft versions should carry the mapped target file set.",
        )

        project_change_plans = _request_json(
            client,
            "GET",
            f"/planning/projects/{project['id']}/change-plans",
            expected_status=200,
        )
        task_change_plans = _request_json(
            client,
            "GET",
            f"/planning/projects/{project['id']}/change-plans?task_id={task['id']}",
            expected_status=200,
        )
        _assert(
            len(project_change_plans) == 1 and len(task_change_plans) == 1,
            "Project and task scoped list endpoints should expose the same Day06 mapping.",
        )
        _assert(
            task_change_plans[0]["task_id"] == task["id"],
            "Task-scoped Day06 mapping should remain tied to the source task.",
        )

        appended_plan = _request_json(
            client,
            "POST",
            f"/planning/change-plans/{created_plan['id']}/versions",
            expected_status=200,
            json_body={
                "title": "Day06 ChangePlan 草案",
                "primary_deliverable_id": deliverable["id"],
                "related_deliverable_ids": [deliverable["id"]],
                "intent_summary": "在保持 Day06 范围收口的前提下补一版更细的动作拆分。",
                "source_summary": context_pack["source_summary"],
                "focus_terms": context_pack["focus_terms"],
                "target_files": target_files,
                "expected_actions": [
                    "追加版本历史查询",
                    "补项目详情中的任务反查映射",
                ],
                "risk_notes": [
                    "继续不进入 Day07 批次",
                    "继续不做产品内真实 Git 写操作",
                ],
                "verification_commands": [
                    "runtime/orchestrator/.venv/Scripts/python.exe runtime/orchestrator/scripts/v4b_day06_change_plan_smoke.py",
                    "cmd /c npm run build",
                ],
                "context_pack_generated_at": context_pack["generated_at"],
            },
        )
        _assert(
            appended_plan["current_version_number"] == 2,
            "Appending a Day06 draft version should advance the head version number.",
        )
        _assert(
            len(appended_plan["versions"]) == 2,
            "Day06 detail payload should preserve the full version timeline.",
        )
        _assert(
            appended_plan["versions"][0]["version_number"] == 2,
            "The latest Day06 draft version should appear first in the detail payload.",
        )
        _assert(
            appended_plan["versions"][0]["related_deliverables"][0]["deliverable_id"]
            == deliverable["id"],
            "The same deliverable should be able to accumulate multiple Day06 draft versions.",
        )

        detail = _request_json(
            client,
            "GET",
            f"/planning/change-plans/{created_plan['id']}",
            expected_status=200,
        )

    report = {
        "project_id": project["id"],
        "task_id": task["id"],
        "deliverable_id": deliverable["id"],
        "change_plan_id": detail["id"],
        "current_version_number": detail["current_version_number"],
        "version_numbers": [item["version_number"] for item in detail["versions"]],
        "target_files": [item["relative_path"] for item in detail["latest_version"]["target_files"]],
        "verification_commands": detail["latest_version"]["verification_commands"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

