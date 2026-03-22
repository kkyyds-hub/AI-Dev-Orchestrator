"""V3-A Day02 smoke checks for the boss homepage and project overview dashboard."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day02-boss-home-smoke"


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.30"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def main() -> None:
    """Seed a compact scenario and verify the new Day02 overview endpoints."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.project import Project, ProjectStage, ProjectStatus
    from app.domain.run import RunFailureCategory, RunStatus
    from app.domain.task import (
        Task,
        TaskHumanStatus,
        TaskPriority,
        TaskRiskLevel,
        TaskStatus,
    )
    from app.main import app
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository

    init_database()

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)

        execution_project = project_repository.create(
            Project(
                name="Phoenix 官网改版",
                summary="老板先看项目推进面，再决定是否继续下钻到任务执行细节。",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage.EXECUTION,
            )
        )
        verification_project = project_repository.create(
            Project(
                name="Billing Guardrails",
                summary="验证阶段需要人工确认新的账单风控阈值。",
                status=ProjectStatus.ACTIVE,
                stage=ProjectStage.VERIFICATION,
            )
        )
        blocked_project = project_repository.create(
            Project(
                name="Legacy Migration",
                summary="遗留迁移项目暂时挂起，等待老板确认是否继续推进。",
                status=ProjectStatus.ON_HOLD,
                stage=ProjectStage.PLANNING,
            )
        )

        completed_task = task_repository.create(
            Task(
                project_id=execution_project.id,
                title="完成视觉稿整理",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.HIGH,
                input_summary="同步完成设计稿与资源清单。",
            )
        )
        completed_run = run_repository.create_running_run(task_id=completed_task.id)
        run_repository.finish_run(
            completed_run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="设计稿整理完成并已同步到交付目录。",
            prompt_tokens=1200,
            completion_tokens=640,
            estimated_cost=0.0082,
            quality_gate_passed=True,
        )

        running_task = task_repository.create(
            Task(
                project_id=execution_project.id,
                title="开发首页首屏样式",
                status=TaskStatus.RUNNING,
                priority=TaskPriority.HIGH,
                input_summary="继续推进首页首屏组件联调。",
            )
        )
        running_run = run_repository.create_running_run(task_id=running_task.id)
        run_repository.finish_run(
            running_run.id,
            status=RunStatus.RUNNING,
            result_summary="首屏布局已完成，正在联调埋点与响应式细节。",
            prompt_tokens=980,
            completion_tokens=420,
            estimated_cost=0.0065,
        )

        waiting_human_task = task_repository.create(
            Task(
                project_id=verification_project.id,
                title="确认账单阈值回归结果",
                status=TaskStatus.WAITING_HUMAN,
                priority=TaskPriority.URGENT,
                risk_level=TaskRiskLevel.HIGH,
                human_status=TaskHumanStatus.REQUESTED,
                input_summary="等待财务与老板确认新的告警阈值。",
            )
        )
        waiting_run = run_repository.create_running_run(task_id=waiting_human_task.id)
        run_repository.finish_run(
            waiting_run.id,
            status=RunStatus.FAILED,
            result_summary="自动验证发现阈值存在误报，需要人工确认后再放行。",
            prompt_tokens=760,
            completion_tokens=310,
            estimated_cost=0.0048,
            failure_category=RunFailureCategory.VERIFICATION_FAILED,
            quality_gate_passed=False,
        )

        blocked_task = task_repository.create(
            Task(
                project_id=blocked_project.id,
                title="整理历史库表映射",
                status=TaskStatus.BLOCKED,
                priority=TaskPriority.HIGH,
                risk_level=TaskRiskLevel.HIGH,
                input_summary="历史库表映射缺少数据源权限，当前无法继续。",
            )
        )
        blocked_run = run_repository.create_running_run(task_id=blocked_task.id)
        run_repository.finish_run(
            blocked_run.id,
            status=RunStatus.CANCELLED,
            result_summary="因权限审批未完成，迁移任务暂时阻塞。",
            prompt_tokens=420,
            completion_tokens=160,
            estimated_cost=0.0021,
            failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
            quality_gate_passed=False,
        )

        task_repository.create(
            Task(
                title="历史未归档任务",
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                input_summary="保留一条未归属项目的历史任务，验证 Day02 与 V1/V2 共存。",
            )
        )

        session.commit()

    with TestClient(app) as client:
        project_overview_response = client.get("/console/project-overview")
        if project_overview_response.status_code != 200:
            raise SystemExit(
                f"project overview failed: {project_overview_response.status_code}"
            )

        task_console_response = client.get("/tasks/console")
        if task_console_response.status_code != 200:
            raise SystemExit(f"task console failed: {task_console_response.status_code}")

        project_overview = project_overview_response.json()
        task_console = task_console_response.json()

    if project_overview["total_projects"] != 3:
        raise SystemExit(
            f"expected 3 projects, got {project_overview['total_projects']}"
        )
    if project_overview["blocked_projects"] != 2:
        raise SystemExit(
            f"expected 2 blocked projects, got {project_overview['blocked_projects']}"
        )
    if project_overview["unassigned_tasks"] != 1:
        raise SystemExit(
            f"expected 1 unassigned task, got {project_overview['unassigned_tasks']}"
        )
    if project_overview["total_project_tasks"] != 4:
        raise SystemExit(
            f"expected 4 project tasks, got {project_overview['total_project_tasks']}"
        )
    if len(project_overview["projects"]) != 3:
        raise SystemExit(
            f"expected 3 project cards, got {len(project_overview['projects'])}"
        )

    stage_counts = {
        item["stage"]: item["count"] for item in project_overview["stage_distribution"]
    }
    if stage_counts.get("execution") != 1 or stage_counts.get("verification") != 1:
        raise SystemExit(f"unexpected stage distribution: {stage_counts}")
    if stage_counts.get("planning") != 1:
        raise SystemExit(f"planning stage count should be 1: {stage_counts}")

    first_project = project_overview["projects"][0]
    if not first_project["latest_progress_summary"]:
        raise SystemExit("project card should contain latest_progress_summary")
    if not first_project["key_risk_summary"]:
        raise SystemExit("project card should contain key_risk_summary")

    risk_codes = {project["name"]: project["risk_level"] for project in project_overview["projects"]}
    if risk_codes.get("Legacy Migration") != "danger":
        raise SystemExit(f"Legacy Migration should be danger, got: {risk_codes}")
    if risk_codes.get("Billing Guardrails") != "warning":
        raise SystemExit(f"Billing Guardrails should be warning, got: {risk_codes}")

    if task_console["total_tasks"] != 5:
        raise SystemExit(f"expected 5 tasks in legacy console, got {task_console['total_tasks']}")

    report = {
        "project_overview": {
            "total_projects": project_overview["total_projects"],
            "blocked_projects": project_overview["blocked_projects"],
            "unassigned_tasks": project_overview["unassigned_tasks"],
            "stage_distribution": project_overview["stage_distribution"],
            "projects": [
                {
                    "name": project["name"],
                    "stage": project["stage"],
                    "risk_level": project["risk_level"],
                    "blocked": project["blocked"],
                    "latest_progress_summary": project["latest_progress_summary"],
                    "key_risk_summary": project["key_risk_summary"],
                    "latest_task": project["latest_task"]["title"]
                    if project["latest_task"] is not None
                    else None,
                }
                for project in project_overview["projects"]
            ],
        },
        "legacy_console": {
            "total_tasks": task_console["total_tasks"],
            "running_tasks": task_console["running_tasks"],
            "waiting_human_tasks": task_console["waiting_human_tasks"],
            "blocked_tasks": task_console["blocked_tasks"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
