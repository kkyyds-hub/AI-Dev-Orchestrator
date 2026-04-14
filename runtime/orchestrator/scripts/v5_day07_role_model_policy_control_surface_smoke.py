"""Day07 smoke for Role Model Policy runtime closure and boss control surface fields."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from fastapi.testclient import TestClient


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day07-role-policy-control-surface"

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
    os.environ["DAILY_BUDGET_USD"] = "5.00"
    os.environ["SESSION_BUDGET_USD"] = "5.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _create_fixture() -> tuple[str, str]:
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
                name="Day07 Role Policy Control Surface Smoke",
                summary="Validate preview/worker/console contract for role policy runtime trace.",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage.PLANNING,
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title="Draft planning scope and acceptance criteria",
                input_summary=(
                    "Create a concise planning outline for implementation scope and "
                    "acceptance criteria."
                ),
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.NORMAL,
                acceptance_criteria=[
                    "Planning scope is explicit",
                    "Acceptance criteria are measurable",
                ],
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            )
        )
        session.commit()
        return str(project.id), str(task.id)


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
        project_id, task_id = _create_fixture()

        rules_payload = _request_json(client, "GET", "/strategy/rules", 200)
        rules = rules_payload["rules"]
        stage_overrides = dict(rules.get("stage_model_tier_overrides", {}))
        planning_overrides = dict(stage_overrides.get("planning", {}))
        planning_overrides["product_manager"] = "premium"
        stage_overrides["planning"] = planning_overrides
        rules["stage_model_tier_overrides"] = stage_overrides

        _request_json(client, "PUT", "/strategy/rules", 200, {"rules": rules})

        preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{project_id}/preview",
            200,
        )
        runtime_trace = preview["role_model_policy_runtime"]
        _assert(
            preview["selected_task_id"] == task_id,
            "preview should select the same task that worker executes",
        )
        _assert(
            runtime_trace["source"] == "stage_override",
            f"unexpected role policy source in preview: {runtime_trace['source']}",
        )
        _assert(
            runtime_trace["desired_tier"] == "premium",
            "preview desired tier should follow stage override",
        )
        _assert(
            runtime_trace["final_tier"] in {"premium", "balanced", "economy"},
            "preview should return a valid final tier",
        )

        worker_result = _request_json(client, "POST", "/workers/run-once", 200)
        _assert(worker_result["claimed"], "worker should claim the Day07 fixture task")
        _assert(worker_result["task_id"] == task_id, "worker selected unexpected task")
        _assert(
            worker_result["role_model_policy_source"] == "stage_override",
            "worker response should expose role model policy runtime source",
        )
        _assert(
            worker_result["role_model_policy_source"] == runtime_trace["source"],
            "worker role policy source should match strategy preview runtime source",
        )
        _assert(
            worker_result["role_model_policy_final_tier"] == runtime_trace["final_tier"],
            "worker final tier should match strategy preview runtime final tier",
        )
        _assert(
            worker_result["provider_key"] == "openai",
            "worker response should expose provider key on provider path",
        )
        _assert(
            worker_result["prompt_template_key"] == "task_execution.default",
            "worker response should expose prompt template contract key",
        )
        _assert(
            worker_result["token_accounting_mode"] in {"provider_reported", "heuristic"},
            "worker response should expose token accounting mode",
        )
        _assert(
            worker_result["run_created_at"] is not None,
            "worker response should expose run_created_at",
        )
        _assert(
            worker_result["run_finished_at"] is not None,
            "worker response should expose run_finished_at",
        )
        _assert(
            worker_result["total_tokens"] is not None and worker_result["total_tokens"] > 0,
            "worker response should expose positive token totals",
        )

        project_overview = _request_json(client, "GET", "/console/project-overview", 200)
        project_item = _find_project_item(project_overview, project_id=project_id)
        latest_task = project_item.get("latest_task")
        _assert(isinstance(latest_task, dict), "console project item missing latest_task")
        _assert(
            latest_task["task_id"] == task_id,
            "console latest_task should match the executed task",
        )
        _assert(
            latest_task["latest_run_id"] == worker_result["run_id"],
            "console latest run id should match worker run id",
        )
        _assert(
            latest_task["latest_run_provider_key"] == worker_result["provider_key"],
            "console latest run provider key should map from run record",
        )
        _assert(
            latest_task["latest_run_prompt_template_key"]
            == worker_result["prompt_template_key"],
            "console latest run prompt template key should map from run record",
        )
        _assert(
            latest_task["latest_run_token_accounting_mode"]
            == worker_result["token_accounting_mode"],
            "console latest run accounting mode should map from run record",
        )
        _assert(
            latest_task["latest_run_prompt_char_count"] == worker_result["prompt_char_count"],
            "console latest run prompt char count should map from run record",
        )
        _assert(
            latest_task["latest_run_estimated_cost"] == worker_result["estimated_cost"],
            "console latest run estimated cost should map from run record",
        )
        _assert(
            latest_task["latest_run_status"] == worker_result["run_status"],
            "console latest run status should map from run record",
        )
        _assert(
            latest_task["latest_run_created_at"] is not None,
            "console latest run created_at should be present",
        )
        _assert(
            latest_task["latest_run_finished_at"] is not None,
            "console latest run finished_at should be present",
        )
        _assert(
            latest_task["latest_run_created_at"] == worker_result["run_created_at"],
            "console latest run created_at should match worker run_created_at",
        )
        _assert(
            latest_task["latest_run_finished_at"] == worker_result["run_finished_at"],
            "console latest run finished_at should match worker run_finished_at",
        )
        _assert(
            latest_task["latest_run_role_model_policy_source"]
            == worker_result["role_model_policy_source"],
            "console latest run role policy source should map from strategy decision",
        )
        _assert(
            latest_task["latest_run_role_model_policy_final_tier"]
            == worker_result["role_model_policy_final_tier"],
            "console latest run final tier should map from strategy decision",
        )

        tasks_console_payload = _request_json(client, "GET", "/tasks/console", 200)
        task_console_item = _find_task_item(tasks_console_payload, task_id=task_id)
        task_console_latest_run = task_console_item.get("latest_run")
        _assert(
            isinstance(task_console_latest_run, dict),
            "tasks console should expose latest_run for executed task",
        )
        _assert(
            task_console_latest_run["id"] == worker_result["run_id"],
            "tasks console latest_run id should match worker run_id",
        )
        _assert(
            task_console_latest_run["status"] == worker_result["run_status"],
            "tasks console latest_run status should match worker run_status",
        )
        _assert(
            task_console_latest_run["created_at"] == worker_result["run_created_at"],
            "tasks console latest_run created_at should match worker run_created_at",
        )
        _assert(
            task_console_latest_run["finished_at"] == worker_result["run_finished_at"],
            "tasks console latest_run finished_at should match worker run_finished_at",
        )
        _assert(
            task_console_latest_run["provider_key"] == worker_result["provider_key"],
            "tasks console latest_run provider_key should match worker provider_key",
        )
        _assert(
            task_console_latest_run["prompt_template_key"]
            == worker_result["prompt_template_key"],
            (
                "tasks console latest_run prompt_template_key should match "
                "worker prompt_template_key"
            ),
        )
        _assert(
            task_console_latest_run["token_accounting_mode"]
            == worker_result["token_accounting_mode"],
            (
                "tasks console latest_run token_accounting_mode should match "
                "worker token_accounting_mode"
            ),
        )
        _assert(
            task_console_latest_run["total_tokens"] == worker_result["total_tokens"],
            "tasks console latest_run total_tokens should match worker total_tokens",
        )
        _assert(
            task_console_latest_run["role_model_policy_source"]
            == worker_result["role_model_policy_source"],
            (
                "tasks console latest_run role_model_policy_source should match "
                "worker role_model_policy_source"
            ),
        )
        _assert(
            task_console_latest_run["role_model_policy_final_tier"]
            == worker_result["role_model_policy_final_tier"],
            (
                "tasks console latest_run role_model_policy_final_tier should match "
                "worker role_model_policy_final_tier"
            ),
        )
        strategy_decision = task_console_latest_run.get("strategy_decision")
        _assert(
            isinstance(strategy_decision, dict),
            "tasks console latest_run should expose strategy_decision payload",
        )
        _assert(
            strategy_decision.get("role_model_policy_source")
            == worker_result["role_model_policy_source"],
            (
                "tasks console strategy_decision role_model_policy_source should match "
                "worker runtime source"
            ),
        )
        _assert(
            strategy_decision.get("role_model_policy_final_tier")
            == worker_result["role_model_policy_final_tier"],
            (
                "tasks console strategy_decision role_model_policy_final_tier should match "
                "worker runtime final tier"
            ),
        )

        task_detail_payload = _request_json(client, "GET", f"/tasks/{task_id}/detail", 200)
        task_detail_latest_run = task_detail_payload.get("latest_run")
        _assert(
            isinstance(task_detail_latest_run, dict),
            "task detail should expose latest_run for executed task",
        )
        _assert(
            task_detail_latest_run["id"] == worker_result["run_id"],
            "task detail latest_run id should match worker run_id",
        )
        _assert(
            task_detail_latest_run["created_at"] == worker_result["run_created_at"],
            "task detail latest_run created_at should match worker run_created_at",
        )
        _assert(
            task_detail_latest_run["finished_at"] == worker_result["run_finished_at"],
            "task detail latest_run finished_at should match worker run_finished_at",
        )
        _assert(
            task_detail_latest_run["provider_key"] == worker_result["provider_key"],
            "task detail latest_run provider_key should match worker provider_key",
        )
        _assert(
            task_detail_latest_run["prompt_template_key"]
            == worker_result["prompt_template_key"],
            (
                "task detail latest_run prompt_template_key should match "
                "worker prompt_template_key"
            ),
        )
        _assert(
            task_detail_latest_run["token_accounting_mode"]
            == worker_result["token_accounting_mode"],
            (
                "task detail latest_run token_accounting_mode should match "
                "worker token_accounting_mode"
            ),
        )
        _assert(
            task_detail_latest_run["total_tokens"] == worker_result["total_tokens"],
            "task detail latest_run total_tokens should match worker total_tokens",
        )
        _assert(
            task_detail_latest_run["role_model_policy_source"]
            == worker_result["role_model_policy_source"],
            (
                "task detail latest_run role_model_policy_source should match "
                "worker role_model_policy_source"
            ),
        )
        _assert(
            task_detail_latest_run["role_model_policy_final_tier"]
            == worker_result["role_model_policy_final_tier"],
            (
                "task detail latest_run role_model_policy_final_tier should match "
                "worker role_model_policy_final_tier"
            ),
        )
        task_detail_strategy_decision = task_detail_latest_run.get("strategy_decision")
        _assert(
            isinstance(task_detail_strategy_decision, dict),
            "task detail latest_run should expose strategy_decision payload",
        )
        _assert(
            task_detail_strategy_decision.get("role_model_policy_source")
            == worker_result["role_model_policy_source"],
            (
                "task detail strategy_decision role_model_policy_source should match "
                "worker runtime source"
            ),
        )
        _assert(
            task_detail_strategy_decision.get("role_model_policy_final_tier")
            == worker_result["role_model_policy_final_tier"],
            (
                "task detail strategy_decision role_model_policy_final_tier should match "
                "worker runtime final tier"
            ),
        )

        task_runs_payload = _request_json(client, "GET", f"/tasks/{task_id}/runs", 200)
        _assert(
            isinstance(task_runs_payload, list) and len(task_runs_payload) > 0,
            "task runs endpoint should expose latest run history for executed task",
        )
        task_runs_latest = task_runs_payload[0]
        _assert(
            task_runs_latest["id"] == worker_result["run_id"],
            "task runs latest id should match worker run_id",
        )
        _assert(
            task_runs_latest["status"] == worker_result["run_status"],
            "task runs latest status should match worker run_status",
        )
        _assert(
            task_runs_latest["created_at"] == worker_result["run_created_at"],
            "task runs latest created_at should match worker run_created_at",
        )
        _assert(
            task_runs_latest["finished_at"] == worker_result["run_finished_at"],
            "task runs latest finished_at should match worker run_finished_at",
        )
        _assert(
            task_runs_latest["provider_key"] == worker_result["provider_key"],
            "task runs latest provider_key should match worker provider_key",
        )
        _assert(
            task_runs_latest["prompt_template_key"] == worker_result["prompt_template_key"],
            "task runs latest prompt_template_key should match worker prompt_template_key",
        )
        _assert(
            task_runs_latest["token_accounting_mode"] == worker_result["token_accounting_mode"],
            "task runs latest token_accounting_mode should match worker token_accounting_mode",
        )
        _assert(
            task_runs_latest["total_tokens"] == worker_result["total_tokens"],
            "task runs latest total_tokens should match worker total_tokens",
        )
        _assert(
            task_runs_latest["role_model_policy_source"]
            == worker_result["role_model_policy_source"],
            (
                "task runs latest role_model_policy_source should match "
                "worker role_model_policy_source"
            ),
        )
        _assert(
            task_runs_latest["role_model_policy_final_tier"]
            == worker_result["role_model_policy_final_tier"],
            (
                "task runs latest role_model_policy_final_tier should match "
                "worker role_model_policy_final_tier"
            ),
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "project_id": project_id,
                "task_id": task_id,
                "preview_role_model_policy_runtime": runtime_trace,
                "worker_snapshot": {
                    "run_id": worker_result["run_id"],
                    "provider_key": worker_result["provider_key"],
                    "prompt_template_key": worker_result["prompt_template_key"],
                    "token_accounting_mode": worker_result["token_accounting_mode"],
                    "total_tokens": worker_result["total_tokens"],
                    "run_created_at": worker_result["run_created_at"],
                    "run_finished_at": worker_result["run_finished_at"],
                    "role_model_policy_source": worker_result["role_model_policy_source"],
                    "role_model_policy_final_tier": worker_result[
                        "role_model_policy_final_tier"
                    ],
                },
                "project_latest_run_snapshot": {
                    "latest_run_id": latest_task["latest_run_id"],
                    "latest_run_provider_key": latest_task["latest_run_provider_key"],
                    "latest_run_prompt_template_key": latest_task[
                        "latest_run_prompt_template_key"
                    ],
                    "latest_run_prompt_char_count": latest_task[
                        "latest_run_prompt_char_count"
                    ],
                    "latest_run_token_accounting_mode": latest_task[
                        "latest_run_token_accounting_mode"
                    ],
                    "latest_run_estimated_cost": latest_task[
                        "latest_run_estimated_cost"
                    ],
                    "latest_run_created_at": latest_task["latest_run_created_at"],
                    "latest_run_finished_at": latest_task["latest_run_finished_at"],
                    "latest_run_role_model_policy_source": latest_task[
                        "latest_run_role_model_policy_source"
                    ],
                    "latest_run_role_model_policy_final_tier": latest_task[
                        "latest_run_role_model_policy_final_tier"
                    ],
                },
                "task_console_latest_run_snapshot": {
                    "run_id": task_console_latest_run["id"],
                    "status": task_console_latest_run["status"],
                    "created_at": task_console_latest_run["created_at"],
                    "finished_at": task_console_latest_run["finished_at"],
                    "provider_key": task_console_latest_run["provider_key"],
                    "prompt_template_key": task_console_latest_run[
                        "prompt_template_key"
                    ],
                    "token_accounting_mode": task_console_latest_run[
                        "token_accounting_mode"
                    ],
                    "total_tokens": task_console_latest_run["total_tokens"],
                    "role_model_policy_source": strategy_decision[
                        "role_model_policy_source"
                    ],
                    "role_model_policy_final_tier": strategy_decision[
                        "role_model_policy_final_tier"
                    ],
                },
                "task_detail_latest_run_snapshot": {
                    "run_id": task_detail_latest_run["id"],
                    "created_at": task_detail_latest_run["created_at"],
                    "finished_at": task_detail_latest_run["finished_at"],
                    "provider_key": task_detail_latest_run["provider_key"],
                    "prompt_template_key": task_detail_latest_run[
                        "prompt_template_key"
                    ],
                    "token_accounting_mode": task_detail_latest_run[
                        "token_accounting_mode"
                    ],
                    "total_tokens": task_detail_latest_run["total_tokens"],
                    "role_model_policy_source": task_detail_strategy_decision[
                        "role_model_policy_source"
                    ],
                    "role_model_policy_final_tier": task_detail_strategy_decision[
                        "role_model_policy_final_tier"
                    ],
                },
                "task_runs_latest_snapshot": {
                    "run_id": task_runs_latest["id"],
                    "status": task_runs_latest["status"],
                    "created_at": task_runs_latest["created_at"],
                    "finished_at": task_runs_latest["finished_at"],
                    "provider_key": task_runs_latest["provider_key"],
                    "prompt_template_key": task_runs_latest["prompt_template_key"],
                    "token_accounting_mode": task_runs_latest["token_accounting_mode"],
                    "total_tokens": task_runs_latest["total_tokens"],
                    "role_model_policy_source": task_runs_latest[
                        "role_model_policy_source"
                    ],
                    "role_model_policy_final_tier": task_runs_latest[
                        "role_model_policy_final_tier"
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
