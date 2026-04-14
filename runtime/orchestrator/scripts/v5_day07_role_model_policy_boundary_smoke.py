"""Day07 smoke for Role Model Policy boundary and degraded-path regression."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID

from fastapi.testclient import TestClient


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "day07-role-policy-boundary-smoke"

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
    os.environ["DAILY_BUDGET_USD"] = "2.00"
    os.environ["SESSION_BUDGET_USD"] = "2.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _create_fixture(
    *,
    project_name: str,
    project_stage: str,
    task_title: str,
    task_input_summary: str,
    owner_role_code: str | None,
    task_priority: str = "high",
    task_risk_level: str = "normal",
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
                summary="Day07 role policy boundary smoke fixture.",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage(project_stage),
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title=task_title,
                input_summary=task_input_summary,
                priority=TaskPriority(task_priority),
                risk_level=TaskRiskLevel(task_risk_level),
                acceptance_criteria=[
                    "Role model policy source is observable",
                    "Runtime tiers are persisted and visible",
                ],
                owner_role_code=(
                    ProjectRoleCode(owner_role_code)
                    if owner_role_code is not None
                    else None
                ),
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


def _seed_budget_usage(task_id: str, estimated_cost: float) -> None:
    from uuid import UUID

    from app.core.db import SessionLocal
    from app.domain.run import RunStatus
    from app.repositories.run_repository import RunRepository

    with SessionLocal() as session:
        run_repository = RunRepository(session)
        run = run_repository.create_running_run(
            task_id=UUID(task_id),
            model_name="gpt-4.1",
            route_reason="Budget usage seeding for Day07 boundary smoke.",
        )
        run_repository.finish_run(
            run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="Budget usage seed run.",
            provider_key="openai",
            prompt_template_key="task_execution.default",
            prompt_template_version="day06.step1",
            token_accounting_mode="provider_reported",
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            estimated_cost=estimated_cost,
            token_pricing_source="mock_provider.receipt.v1",
        )
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


def main() -> None:
    _prepare_env()

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        stage_override_project_id, stage_override_task_id = _create_fixture(
            project_name="Day07 Stage Override Source Fixture",
            project_stage="planning",
            task_title="Plan delivery scope and milestones",
            task_input_summary="Create planning scope and milestones for this project.",
            owner_role_code="product_manager",
        )
        role_preference_project_id, role_preference_task_id = _create_fixture(
            project_name="Day07 Role Preference Source Fixture",
            project_stage="execution",
            task_title="Clarify cross-team execution alignment",
            task_input_summary="Align execution plan across teams and constraints.",
            owner_role_code="product_manager",
        )
        budget_fallback_project_id, budget_fallback_task_id = _create_fixture(
            project_name="Day07 Budget Fallback Source Fixture",
            project_stage="execution",
            task_title="Refine architecture execution guardrail",
            task_input_summary="Refine architecture guardrail with dependency notes.",
            owner_role_code="architect",
        )

        rules_payload = _request_json(client, "GET", "/strategy/rules", 200)
        rules = rules_payload["rules"]
        stage_overrides = dict(rules.get("stage_model_tier_overrides", {}))
        planning_overrides = dict(stage_overrides.get("planning", {}))
        planning_overrides["product_manager"] = "premium"
        stage_overrides["planning"] = planning_overrides
        rules["stage_model_tier_overrides"] = stage_overrides

        role_preferences = dict(rules.get("role_model_tier_preferences", {}))
        role_preferences.pop("architect", None)
        rules["role_model_tier_preferences"] = role_preferences

        _request_json(client, "PUT", "/strategy/rules", 200, {"rules": rules})

        stage_override_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{stage_override_project_id}/preview",
            200,
        )
        stage_runtime = stage_override_preview["role_model_policy_runtime"]
        _assert(
            stage_runtime["source"] == "stage_override",
            f"unexpected stage override source: {stage_runtime['source']}",
        )
        _assert(
            stage_runtime["desired_tier"] == "premium",
            "stage override desired tier should be premium",
        )
        _assert(
            stage_runtime["stage_override_applied"] is True,
            "stage override should be flagged as applied",
        )

        _set_task_completed(stage_override_task_id)

        role_preference_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{role_preference_project_id}/preview",
            200,
        )
        role_preference_runtime = role_preference_preview["role_model_policy_runtime"]
        _assert(
            role_preference_runtime["source"] == "role_preference",
            (
                "execution/product_manager fixture should use role_preference source, "
                f"got {role_preference_runtime['source']}"
            ),
        )
        _assert(
            role_preference_runtime["stage_override_applied"] is False,
            "role_preference path should not apply stage override",
        )

        _set_task_completed(role_preference_task_id)

        budget_fallback_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{budget_fallback_project_id}/preview",
            200,
        )
        budget_fallback_runtime = budget_fallback_preview["role_model_policy_runtime"]
        _assert(
            budget_fallback_runtime["source"] == "budget_fallback",
            (
                "architect fixture should fall back to budget source after preference removal, "
                f"got {budget_fallback_runtime['source']}"
            ),
        )
        _assert(
            budget_fallback_runtime["stage_override_applied"] is False,
            "budget_fallback path should not apply stage override",
        )

        worker_result = _request_json(client, "POST", "/workers/run-once", 200)
        _assert(worker_result["claimed"], "worker should claim budget_fallback fixture task")
        _assert(
            worker_result["task_id"] == budget_fallback_task_id,
            "worker should run the budget_fallback fixture task",
        )
        _assert(
            worker_result["role_model_policy_source"] == "budget_fallback",
            "worker response should expose budget_fallback runtime source",
        )

        budget_seed_project_id, budget_seed_task_id = _create_fixture(
            project_name="Day07 Critical Budget Capping Fixture",
            project_stage="planning",
            task_title="Plan critical verification scope",
            task_input_summary="Plan and verify under critical budget pressure.",
            owner_role_code="product_manager",
            task_priority="urgent",
            task_risk_level="high",
        )
        _seed_budget_usage(stage_override_task_id, estimated_cost=1.8)

        critical_preview = _request_json(
            client,
            "GET",
            f"/strategy/projects/{budget_seed_project_id}/preview",
            200,
        )
        critical_runtime = critical_preview["role_model_policy_runtime"]
        _assert(
            critical_preview["budget_pressure_level"] == "critical",
            (
                "critical budget fixture should run under critical pressure, "
                f"got {critical_preview['budget_pressure_level']}"
            ),
        )
        _assert(
            critical_runtime["source"] == "stage_override",
            "critical fixture should still report stage_override as policy source",
        )
        _assert(
            critical_runtime["desired_tier"] == "premium",
            "critical fixture desired tier should keep stage override premium",
        )
        _assert(
            critical_runtime["final_tier"] == "economy",
            "critical budget should cap final tier to economy",
        )

        overview_payload = _request_json(client, "GET", "/console/project-overview", 200)
        project_item = _find_project_item(
            overview_payload,
            project_id=budget_fallback_project_id,
        )
        latest_task = project_item.get("latest_task")
        _assert(
            isinstance(latest_task, dict),
            "console project item should expose latest_task for budget fallback fixture",
        )
        _assert(
            latest_task["latest_run_role_model_policy_source"] == "budget_fallback",
            "console latest_run role policy source should preserve budget_fallback",
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "stage_override_case": {
                    "project_id": stage_override_project_id,
                    "task_id": stage_override_task_id,
                    "runtime": stage_runtime,
                },
                "role_preference_case": {
                    "project_id": role_preference_project_id,
                    "task_id": role_preference_task_id,
                    "runtime": role_preference_runtime,
                },
                "budget_fallback_case": {
                    "project_id": budget_fallback_project_id,
                    "task_id": budget_fallback_task_id,
                    "preview_runtime": budget_fallback_runtime,
                    "worker_runtime": {
                        "run_id": worker_result["run_id"],
                        "source": worker_result["role_model_policy_source"],
                        "final_tier": worker_result["role_model_policy_final_tier"],
                    },
                    "console_runtime_source": latest_task[
                        "latest_run_role_model_policy_source"
                    ],
                },
                "critical_budget_case": {
                    "project_id": budget_seed_project_id,
                    "task_id": budget_seed_task_id,
                    "budget_pressure_level": critical_preview["budget_pressure_level"],
                    "runtime": critical_runtime,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
