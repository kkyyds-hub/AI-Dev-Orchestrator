"""V3-D Day15 smoke checks for strategy engine and model-role routing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import UUID


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day15-strategy-engine-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _create_fixture():
    from app.core.db import SessionLocal
    from app.domain.project import Project, ProjectStage, ProjectStatus
    from app.domain.project_role import ProjectRoleCode
    from app.domain.task import Task, TaskPriority, TaskRiskLevel, TaskStatus
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)

        project = project_repository.create(
            Project(
                name="Day15 策略路由烟测项目",
                summary="验证项目阶段、角色、预算压力与 Skill 绑定能共同驱动模型路由。",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage.PLANNING,
            )
        )

        planning_task = task_repository.create(
            Task(
                project_id=project.id,
                title="澄清需求范围并补齐规划说明",
                input_summary="simulate: 产出规划阶段需要的需求澄清、范围边界和优先级说明。",
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.NORMAL,
                acceptance_criteria=[
                    "补齐需求澄清结论",
                    "给出范围边界与优先级说明",
                ],
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        engineering_task = task_repository.create(
            Task(
                project_id=project.id,
                title="实现联调脚本并记录变更摘要",
                input_summary="simulate: 生成执行阶段需要的联调脚本和变更摘要。",
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.HIGH,
                acceptance_criteria=[
                    "生成联调脚本说明",
                    "补齐变更摘要",
                ],
                owner_role_code=ProjectRoleCode.ENGINEER,
                upstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        budget_task = task_repository.create(
            Task(
                project_id=project.id,
                title="历史预算消耗样本",
                input_summary="simulate: 写入一条历史运行成本样本。",
                priority=TaskPriority.LOW,
                risk_level=TaskRiskLevel.LOW,
                acceptance_criteria=["仅用于预算压力计算"],
                owner_role_code=ProjectRoleCode.REVIEWER,
                status=TaskStatus.COMPLETED,
            )
        )
        session.commit()

    return project, planning_task, engineering_task, budget_task


def _create_budget_sample_run(*, budget_task_id):
    from app.core.db import SessionLocal
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunStatus
    from app.repositories.run_repository import RunRepository

    with SessionLocal() as session:
        run_repository = RunRepository(session)
        budget_run = run_repository.create_running_run(
            task_id=budget_task_id,
            model_name="gpt-4.1",
            route_reason="历史成本样本，用于把预算压到 critical。",
            owner_role_code=ProjectRoleCode.REVIEWER,
        )
        budget_run = run_repository.finish_run(
            budget_run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="历史预算样本完成。",
            estimated_cost=0.09,
        )
        session.commit()

    return budget_run


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.main import app
    from app.repositories.run_repository import RunRepository

    init_database()
    project, planning_task, engineering_task, budget_task = _create_fixture()

    with TestClient(app) as client:
        initial_rules_response = client.get("/strategy/rules")
        _assert(
            initial_rules_response.status_code == 200,
            f"fetch strategy rules failed: {initial_rules_response.status_code}",
        )
        initial_rules_payload = initial_rules_response.json()
        rules = initial_rules_payload["rules"]

        preview_before_override_response = client.get(
            f"/strategy/projects/{project.id}/preview"
        )
        _assert(
            preview_before_override_response.status_code == 200,
            f"strategy preview failed: {preview_before_override_response.status_code}",
        )
        preview_before_override = preview_before_override_response.json()

        _assert(
            preview_before_override["selected_task_id"] == str(planning_task.id),
            "planning stage should prefer the product/planning task",
        )
        _assert(
            "requirements_clarification" in preview_before_override["selected_skill_codes"],
            "planning/product task should inherit Day13 planning skills",
        )
        _assert(
            preview_before_override["budget_pressure_level"] == "normal",
            "fresh runtime should start with normal budget pressure",
        )

        stage_overrides = dict(rules.get("stage_model_tier_overrides", {}))
        planning_overrides = dict(stage_overrides.get("planning", {}))
        planning_overrides["product_manager"] = "premium"
        stage_overrides["planning"] = planning_overrides
        rules["stage_model_tier_overrides"] = stage_overrides

        update_rules_response = client.put(
            "/strategy/rules",
            json={"rules": rules},
        )
        _assert(
            update_rules_response.status_code == 200,
            f"update strategy rules failed: {update_rules_response.status_code}",
        )

        preview_after_override_response = client.get(
            f"/strategy/projects/{project.id}/preview"
        )
        _assert(
            preview_after_override_response.status_code == 200,
            f"strategy preview after override failed: {preview_after_override_response.status_code}",
        )
        preview_after_override = preview_after_override_response.json()

        _assert(
            preview_after_override["model_tier"] == "premium",
            "rule override should promote the planning/product route to premium under normal budget",
        )
        _assert(
            preview_after_override["model_name"] == "gpt-5",
            "premium profile should map to gpt-5 in the default rules",
        )

        budget_run = _create_budget_sample_run(budget_task_id=budget_task.id)

        preview_under_pressure_response = client.get(
            f"/strategy/projects/{project.id}/preview"
        )
        _assert(
            preview_under_pressure_response.status_code == 200,
            f"strategy preview under pressure failed: {preview_under_pressure_response.status_code}",
        )
        preview_under_pressure = preview_under_pressure_response.json()

        _assert(
            preview_under_pressure["budget_pressure_level"] == "critical",
            "historical cost sample should push budget pressure to critical",
        )
        _assert(
            preview_under_pressure["budget_action"] == "degraded",
            "critical budget should degrade strategy action",
        )
        _assert(
            preview_under_pressure["model_tier"] == "economy",
            "critical budget should cap model tier back to economy",
        )
        _assert(
            preview_under_pressure["model_name"] == "gpt-4.1-mini",
            "economy profile should map to gpt-4.1-mini in the default rules",
        )
        _assert(
            any(
                reason["code"] == "budget_pressure"
                for reason in preview_under_pressure["strategy_reasons"]
            ),
            "strategy preview should expose explainable reasons",
        )

        worker_response = client.post("/workers/run-once")
        _assert(
            worker_response.status_code == 200,
            f"run worker once failed: {worker_response.status_code}",
        )
        worker_payload = worker_response.json()

    _assert(worker_payload["claimed"], "worker should claim one project task")
    _assert(
        worker_payload["task_id"] == str(planning_task.id),
        "worker should execute the strategy-selected planning task",
    )
    _assert(
        worker_payload["model_name"] == "gpt-4.1-mini",
        "worker response should expose the routed model name",
    )
    _assert(
        worker_payload["strategy_code"],
        "worker response should expose a strategy code",
    )
    _assert(
        worker_payload["selected_skill_names"],
        "worker response should expose selected skill names",
    )

    with SessionLocal() as session:
        persisted_run = RunRepository(session).get_by_id(UUID(worker_payload["run_id"]))

    _assert(persisted_run is not None, "worker run should persist")
    _assert(
        persisted_run.strategy_decision is not None,
        "persisted run should include strategy decision snapshot",
    )
    _assert(
        persisted_run.strategy_decision.model_tier == "economy",
        "persisted run strategy decision should keep the selected model tier",
    )

    report = {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "planning_task_id": str(planning_task.id),
            "engineering_task_id": str(engineering_task.id),
        },
        "rules_source": initial_rules_payload["source"],
        "budget_sample_run": {
            "run_id": str(budget_run.id),
            "estimated_cost": budget_run.estimated_cost,
        },
        "preview": {
            "before_override_model_tier": preview_before_override["model_tier"],
            "after_override_model_tier": preview_after_override["model_tier"],
            "under_pressure_budget_pressure": preview_under_pressure["budget_pressure_level"],
            "under_pressure_model_name": preview_under_pressure["model_name"],
            "selected_skill_codes": preview_under_pressure["selected_skill_codes"],
            "strategy_reason_codes": [
                reason["code"] for reason in preview_under_pressure["strategy_reasons"]
            ],
        },
        "worker": {
            "task_id": worker_payload["task_id"],
            "run_id": worker_payload["run_id"],
            "model_name": worker_payload["model_name"],
            "model_tier": worker_payload["model_tier"],
            "strategy_code": worker_payload["strategy_code"],
            "selected_skill_names": worker_payload["selected_skill_names"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
