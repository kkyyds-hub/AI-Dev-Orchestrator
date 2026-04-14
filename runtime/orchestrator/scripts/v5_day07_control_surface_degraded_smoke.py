"""Day07 degraded-path smoke for control-surface boundary coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day07-control-surface-degraded-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    expected_status: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.request(method, path, json=payload)
    if response.status_code != expected_status:
        raise SystemExit(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _create_project_with_task(
    *,
    project_name: str,
    project_stage: str,
    task_title: str,
    task_input_summary: str,
    owner_role_code: str | None,
    depends_on_task_ids: list[UUID] | None = None,
) -> tuple[str, str]:
    from app.core.db import SessionLocal
    from app.domain.project import Project, ProjectStage, ProjectStatus
    from app.domain.project_role import ProjectRoleCode
    from app.domain.task import Task, TaskPriority, TaskRiskLevel
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)
        project = project_repository.create(
            Project(
                name=project_name,
                summary="Day07 degraded smoke fixture.",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage(project_stage),
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title=task_title,
                input_summary=task_input_summary,
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.NORMAL,
                acceptance_criteria=[
                    "Control-surface field mapping is stable",
                    "Role policy runtime source is observable",
                ],
                owner_role_code=(
                    ProjectRoleCode(owner_role_code)
                    if owner_role_code is not None
                    else None
                ),
                depends_on_task_ids=depends_on_task_ids or [],
            )
        )
        session.commit()
        return str(project.id), str(task.id)


def _set_task_completed(task_id: str) -> None:
    from app.core.db import SessionLocal
    from app.domain.task import TaskStatus
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        TaskRepository(session).set_status(UUID(task_id), TaskStatus.COMPLETED)
        session.commit()


def _find_project_item(
    overview_payload: dict[str, object],
    *,
    project_id: str,
) -> dict[str, object]:
    projects = overview_payload.get("projects")
    _assert(isinstance(projects, list), "console overview missing projects list")
    for item in projects:
        if isinstance(item, dict) and item.get("id") == project_id:
            return item
    raise SystemExit(f"project not found in console overview: {project_id}")


def _find_task_item(
    tasks_payload: dict[str, object],
    *,
    task_id: str,
) -> dict[str, object]:
    tasks = tasks_payload.get("tasks")
    _assert(isinstance(tasks, list), "tasks console payload missing tasks list")
    for item in tasks:
        if isinstance(item, dict) and item.get("id") == task_id:
            return item
    raise SystemExit(f"task not found in tasks console payload: {task_id}")


def main() -> None:
    _prepare_env()

    from app.main import create_application

    app = create_application()
    with TestClient(app) as client:
        no_project_overview = _request_json(client, "GET", "/console/project-overview", 200)
        _assert(
            no_project_overview["total_projects"] == 0,
            "empty runtime should expose total_projects=0",
        )
        _assert(
            no_project_overview["projects"] == [],
            "empty runtime should expose empty project list",
        )

        no_project_worker = _request_json(client, "POST", "/workers/run-once", 200)
        _assert(
            no_project_worker["claimed"] is False,
            "worker should not claim when there are no projects/tasks",
        )
        _assert(
            "No pending tasks available for routing." in no_project_worker["message"],
            "worker should return stable no-pending message on empty runtime",
        )

        no_run_project_id, no_run_task_id = _create_project_with_task(
            project_name="Day07 No-Run Mapping Fixture",
            project_stage="planning",
            task_title="Prepare planning draft without execution",
            task_input_summary="Keep this task pending without any run record.",
            owner_role_code="product_manager",
        )

        no_run_overview = _request_json(client, "GET", "/console/project-overview", 200)
        no_run_project_item = _find_project_item(no_run_overview, project_id=no_run_project_id)
        latest_task = no_run_project_item.get("latest_task")
        _assert(isinstance(latest_task, dict), "no-run fixture should expose latest_task")
        _assert(
            latest_task["latest_run_id"] is None,
            "latest_run_id should stay null when no run exists",
        )
        _assert(
            latest_task["latest_run_provider_key"] is None,
            "latest_run_provider_key should stay null when no run exists",
        )
        _assert(
            latest_task["latest_run_prompt_char_count"] is None,
            "latest_run_prompt_char_count should stay null when no run exists",
        )
        _assert(
            latest_task["latest_run_estimated_cost"] is None,
            "latest_run_estimated_cost should stay null when no run exists",
        )
        _assert(
            latest_task["latest_run_created_at"] is None
            and latest_task["latest_run_finished_at"] is None,
            "run timestamps should stay null when no run exists",
        )
        no_run_tasks_console = _request_json(client, "GET", "/tasks/console", 200)
        no_run_task_console_item = _find_task_item(
            no_run_tasks_console,
            task_id=no_run_task_id,
        )
        _assert(
            no_run_task_console_item["latest_run"] is None,
            "tasks console latest_run should stay null when no run exists",
        )
        no_run_task_detail = _request_json(client, "GET", f"/tasks/{no_run_task_id}/detail", 200)
        _assert(
            no_run_task_detail["latest_run"] is None,
            "task detail latest_run should stay null when no run exists",
        )
        _assert(
            no_run_task_detail["runs"] == [],
            "task detail runs should stay empty when no run exists",
        )
        no_run_task_runs = _request_json(client, "GET", f"/tasks/{no_run_task_id}/runs", 200)
        _assert(
            isinstance(no_run_task_runs, list) and len(no_run_task_runs) == 0,
            "task runs endpoint should stay empty when no run exists",
        )

        _set_task_completed(no_run_task_id)

        blocked_project_id, blocked_task_id = _create_project_with_task(
            project_name="Day07 No-Routable-Task Fixture",
            project_stage="execution",
            task_title="Blocked by missing dependency",
            task_input_summary="This task intentionally depends on a missing task.",
            owner_role_code="engineer",
            depends_on_task_ids=[uuid4()],
        )

        blocked_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{blocked_project_id}/preview",
            200,
        )
        _assert(
            blocked_preview["selected_task_id"] is None,
            "preview should not select task when only blocked candidates exist",
        )
        _assert(
            "none are currently routable" in blocked_preview["message"],
            "preview should expose no-routable summary",
        )

        no_routable_worker = _request_json(client, "POST", "/workers/run-once", 200)
        _assert(
            no_routable_worker["claimed"] is False,
            "worker should not claim when all pending tasks are blocked",
        )
        _assert(
            "none are currently routable" in no_routable_worker["message"],
            "worker should expose no-routable summary",
        )
        blocked_tasks_console = _request_json(client, "GET", "/tasks/console", 200)
        blocked_task_console_item = _find_task_item(
            blocked_tasks_console,
            task_id=blocked_task_id,
        )
        _assert(
            blocked_task_console_item["latest_run"] is None,
            "no-routable task should keep latest_run=null in tasks console",
        )
        blocked_task_detail = _request_json(client, "GET", f"/tasks/{blocked_task_id}/detail", 200)
        _assert(
            blocked_task_detail["latest_run"] is None,
            "no-routable task should keep latest_run=null in task detail",
        )
        _assert(
            blocked_task_detail["runs"] == [],
            "no-routable task should keep empty runs in task detail",
        )
        blocked_task_runs = _request_json(client, "GET", f"/tasks/{blocked_task_id}/runs", 200)
        _assert(
            isinstance(blocked_task_runs, list) and len(blocked_task_runs) == 0,
            "no-routable task should keep empty runs in task runs endpoint",
        )

        fallback_project_id, fallback_task_id = _create_project_with_task(
            project_name="Day07 Budget-Fallback Stable Fixture",
            project_stage="execution",
            task_title="Architecture routing under neutral budget",
            task_input_summary="Route architect-owned work with no explicit role preference.",
            owner_role_code="architect",
        )

        rules_payload = _request_json(client, "GET", "/strategy/rules", 200)
        rules = rules_payload["rules"]

        role_preferences = dict(rules.get("role_model_tier_preferences", {}))
        role_preferences.pop("architect", None)
        rules["role_model_tier_preferences"] = role_preferences

        stage_overrides = dict(rules.get("stage_model_tier_overrides", {}))
        for stage in list(stage_overrides):
            stage_rule = stage_overrides.get(stage)
            if not isinstance(stage_rule, dict):
                continue
            cleaned_rule = dict(stage_rule)
            cleaned_rule.pop("architect", None)
            stage_overrides[stage] = cleaned_rule
        rules["stage_model_tier_overrides"] = stage_overrides

        _request_json(client, "PUT", "/strategy/rules", 200, {"rules": rules})

        fallback_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{fallback_project_id}/preview",
            200,
        )
        fallback_runtime = fallback_preview["role_model_policy_runtime"]
        _assert(
            fallback_preview["budget_pressure_level"] == "normal",
            "fallback fixture should run under normal budget pressure",
        )
        _assert(
            fallback_runtime["source"] == "budget_fallback",
            "without override/preference the role policy source should be budget_fallback",
        )
        _assert(
            fallback_runtime["stage_override_applied"] is False,
            "budget_fallback fixture should not apply stage override",
        )
        _assert(
            fallback_runtime["desired_tier"] == "balanced"
            and fallback_runtime["final_tier"] == "balanced",
            "normal budget fallback should stabilize on balanced tier",
        )

        fallback_worker = _request_json(client, "POST", "/workers/run-once", 200)
        _assert(
            fallback_worker["claimed"] is True,
            "worker should claim budget_fallback fixture task",
        )
        _assert(
            fallback_worker["task_id"] == fallback_task_id,
            "worker should execute the budget_fallback fixture task",
        )
        _assert(
            fallback_worker["role_model_policy_source"] == "budget_fallback",
            "worker response should preserve budget_fallback source",
        )

        fallback_overview = _request_json(client, "GET", "/console/project-overview", 200)
        fallback_project_item = _find_project_item(
            fallback_overview,
            project_id=fallback_project_id,
        )
        fallback_latest_task = fallback_project_item.get("latest_task")
        _assert(
            isinstance(fallback_latest_task, dict),
            "fallback fixture should expose latest_task in console overview",
        )
        _assert(
            fallback_latest_task["latest_run_role_model_policy_source"] == "budget_fallback",
            "console latest run should preserve budget_fallback source",
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "no_project_case": {
                    "total_projects": no_project_overview["total_projects"],
                    "worker_message": no_project_worker["message"],
                },
                "no_run_mapping_case": {
                    "project_id": no_run_project_id,
                    "task_id": no_run_task_id,
                    "latest_run_id": latest_task["latest_run_id"],
                    "latest_run_prompt_char_count": latest_task["latest_run_prompt_char_count"],
                    "latest_run_estimated_cost": latest_task["latest_run_estimated_cost"],
                    "tasks_console_latest_run": no_run_task_console_item["latest_run"],
                    "task_detail_latest_run": no_run_task_detail["latest_run"],
                    "task_runs_count": len(no_run_task_runs),
                },
                "no_routable_case": {
                    "project_id": blocked_project_id,
                    "task_id": blocked_task_id,
                    "preview_message": blocked_preview["message"],
                    "worker_message": no_routable_worker["message"],
                    "tasks_console_latest_run": blocked_task_console_item["latest_run"],
                    "task_detail_latest_run": blocked_task_detail["latest_run"],
                    "task_runs_count": len(blocked_task_runs),
                },
                "budget_fallback_case": {
                    "project_id": fallback_project_id,
                    "task_id": fallback_task_id,
                    "preview_runtime": fallback_runtime,
                    "worker_runtime_source": fallback_worker["role_model_policy_source"],
                    "console_runtime_source": fallback_latest_task[
                        "latest_run_role_model_policy_source"
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
